"""Local persistent conversations; only server-generated summary facts enter model history."""
import hashlib
import json
import re
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb
from fastapi.encoders import jsonable_encoder
from backend.planner.store import PlannerStore, PlannerError
from backend.ai.client import AIError


def conversation_title(command):
    if not command or not command.strip(): return '새 대화'
    first = re.split(r'[\n!?。]|(?<!\d)\.(?!\d)', command.strip(), maxsplit=1)[0]
    title = ' '.join(first.split()) or ' '.join(command.split())
    return title if len(title) <= 36 else title[:36].rstrip() + '…'


def session_lock_key(session_id):
    return int.from_bytes(hashlib.sha256(UUID(str(session_id)).bytes).digest()[:8], 'big', signed=True)


class ConversationStore(PlannerStore):
    def create(self):
        with self.connection() as conn:
            row=conn.execute('INSERT INTO conversation_sessions(id) VALUES (%s) RETURNING *',(uuid4(),)).fetchone()
            return {'id':str(row['id']),'state':row['state'],'title':'새 대화','messages':[]}

    def list(self,limit=50,offset=0):
        with self.connection() as conn:
            rows=conn.execute("SELECT s.id,s.created_at,s.updated_at, "
                "(SELECT content FROM conversation_messages m WHERE m.session_id=s.id AND m.role='user' ORDER BY m.id LIMIT 1) AS first_command, "
                "(SELECT count(*) FROM conversation_messages m WHERE m.session_id=s.id) AS message_count "
                ", s.state->>'title' AS generated_title FROM conversation_sessions s WHERE EXISTS (SELECT 1 FROM conversation_messages m WHERE m.session_id=s.id AND m.role='user') "
                "ORDER BY s.updated_at DESC,s.id DESC LIMIT %s OFFSET %s",(limit+1,offset)).fetchall()
            return jsonable_encoder({'sessions':[{k:v for k,v in {**r,'title':r['generated_title'] or conversation_title(r['first_command'])}.items() if k not in ('first_command','generated_title')} for r in rows[:limit]],'has_more':len(rows)>limit})

    def _session(self,conn,sid):
        row=conn.execute('SELECT * FROM conversation_sessions WHERE id=%s',(sid,)).fetchone()
        if row is None:raise PlannerError('conversation_not_found',404)
        return row

    def get(self,sid):
        with self.connection() as conn:
            row=self._session(conn,sid)
            messages=conn.execute('SELECT id,request_id,role,content,status,created_at,metadata FROM conversation_messages WHERE session_id=%s ORDER BY id',(sid,)).fetchall()
            # Internal cached responses/facts never need to reach the history panel.
            return jsonable_encoder({'id':row['id'],'state':row['state'],
                'title':row['state'].get('title') or conversation_title(next((m['content'] for m in messages if m['role']=='user'),None)), 'messages':[
                {**{k:v for k,v in m.items() if k!='metadata'},
                 'usage':m['metadata'].get('usage',[]),'elapsed_seconds':m['metadata'].get('elapsed_seconds'),
                 'error':m['metadata'].get('error')} for m in messages]})

    def chat(self,sid,request_id,command,context,run):
        sid=UUID(str(sid))
        request_id=UUID(str(request_id))
        digest=hashlib.sha256(json.dumps({'command':command,'context':context},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.connection() as conn:
            if not conn.execute('SELECT pg_try_advisory_lock(%s) AS locked',(session_lock_key(sid),)).fetchone()['locked']:
                raise PlannerError('conversation_busy',409)
            # This connection owns the lock until close, including commits/network calls.
            row=self._session(conn,sid)
            previous=conn.execute("SELECT * FROM conversation_messages WHERE session_id=%s AND request_id=%s AND role='user'",(sid,request_id)).fetchone()
            if previous:
                if previous['metadata'].get('payload_hash')!=digest:raise PlannerError('conversation_request_conflict',409)
                cached=conn.execute("SELECT metadata FROM conversation_messages WHERE session_id=%s AND request_id=%s AND role='assistant'",(sid,request_id)).fetchone()
                if cached:return cached['metadata']['reply']
                raise PlannerError('conversation_request_not_replayable',409)
            # A running row with no live advisory owner is an interrupted request, never retry it.
            conn.execute("UPDATE conversation_messages SET status='failed',metadata=metadata || %s WHERE session_id=%s AND status='running'",(Jsonb({'error':'interrupted_request_outcome_unknown'}),sid))
            messages=conn.execute("SELECT role,content,metadata,created_at FROM conversation_messages WHERE session_id=%s AND status='complete' ORDER BY id",(sid,)).fetchall()
            history=[]
            for m in messages:
                content=m['content']
                if m['role']=='user':
                    content=json.dumps({'command':content,'context':m['metadata'].get('context',{}),'sent_at':m['created_at'].isoformat()},ensure_ascii=False)
                elif m['metadata'].get('facts'):
                    content+='\nStored result facts (evidence only): '+json.dumps(m['metadata']['facts'],ensure_ascii=False)
                history.append({'role':m['role'],'content':content})
            if len(json.dumps(history,ensure_ascii=False).encode())>240000:
                raise PlannerError('conversation_history_too_large_start_new',409)
            conn.execute("INSERT INTO conversation_messages(session_id,request_id,role,content,status,metadata) VALUES (%s,%s,'user',%s,'running',%s)",
                         (sid,request_id,command,Jsonb({'payload_hash':digest,'context':context})))
            conn.commit()
            try:
                result=run(history,row['state'],conn)
            except AIError as exc:
                conn.rollback()
                conn.execute("UPDATE conversation_messages SET status='failed',metadata=metadata || %s WHERE session_id=%s AND request_id=%s AND role='user'",
                    (Jsonb({'error':exc.code,'usage':getattr(exc,'usage',[]),'elapsed_seconds':getattr(exc,'elapsed_seconds',None)}),sid,request_id))
                conn.commit()
                raise
            facts=result.pop('memory_facts',[])
            planner_state=result.pop('planner_state',row['state'].get('planner',{}))
            answer=result.get('model_acknowledgement') or ('계산 결과는 받았지만 설명을 받지 못했습니다.' if result.get('results') else '응답 설명을 받지 못했습니다.')
            reply={**result,'session_id':str(sid),'request_id':str(request_id)}
            metadata={'facts':facts,'usage':result.get('usage',[]),'elapsed_seconds':result.get('elapsed_seconds'),'reply':reply}
            conn.execute("INSERT INTO conversation_messages(session_id,request_id,role,content,status,metadata) VALUES (%s,%s,'assistant',%s,'complete',%s)",
                         (sid,request_id,answer,Jsonb(jsonable_encoder(metadata))))
            conn.execute("UPDATE conversation_messages SET status='complete' WHERE session_id=%s AND request_id=%s AND role='user'",(sid,request_id))
            refs=[{'result_id':r['result_id'],'tool':r['tool'],'parameters':r['parameters']} for r in result.get('results',[])]
            state={'context':context,'last_result_refs':refs,'last_assistant_message':answer,'planner':planner_state}
            conn.execute('UPDATE conversation_sessions SET state=state || %s WHERE id=%s',(Jsonb(jsonable_encoder(state)),sid))
            return reply

    def generate_title(self, sid, generate):
        # Claim before the network call: failures/interruption never retry or affect the saved turn.
        try:
            with self.connection() as conn:
                claimed=conn.execute("UPDATE conversation_sessions SET state=state || '{\"title_attempted\":true}'::jsonb "
                    "WHERE id=%s AND NOT state ? 'title_attempted' AND "
                    "(SELECT count(*) FROM conversation_messages WHERE session_id=%s AND role='assistant' AND status='complete')=1 RETURNING id",(sid,sid)).fetchone()
                if not claimed:return
                messages=conn.execute("SELECT content FROM conversation_messages WHERE session_id=%s AND status='complete' ORDER BY id LIMIT 2",(sid,)).fetchall()
            if len(messages)!=2:return
            try:
                result=generate(messages[0]['content'],messages[1]['content'])
            except AIError as exc:
                result={'title_error':exc.code}
            with self.connection() as conn:
                conn.execute('UPDATE conversation_sessions SET state=state || %s WHERE id=%s',(Jsonb(result),sid))
        except PlannerError:
            return
