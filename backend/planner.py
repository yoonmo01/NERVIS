"""Local planner application functions, shared by HTTP and future model tools."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

from dotenv import dotenv_values
from fastapi.encoders import jsonable_encoder
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from backend.planner_schemas import CourseCreate, MeetingCreate, TaskCreate

ROOT = Path(__file__).resolve().parents[1]
TABLE_MODELS = {'courses': CourseCreate, 'class_meetings': MeetingCreate, 'tasks': TaskCreate}


class PlannerError(Exception):
    def __init__(self, code, status=422):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class DatabaseSettings:
    password: str = field(repr=False)
    port: int = 15432
    dbname: str = 'nervis'

    @classmethod
    def load(cls):
        values = {**dotenv_values(ROOT / '.env.database', interpolate=False), **os.environ}
        try:
            password = values.get('NERVIS_DB_PASSWORD') or ''
            port = int(values.get('NERVIS_DB_PORT') or '15432')
            if not password or not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            raise PlannerError('database_not_configured', 503) from None
        return cls(password, port)

    def connect(self, *, autocommit=False):
        return psycopg.connect(host='127.0.0.1', port=self.port, dbname=self.dbname,
                               user='nervis', password=self.password, connect_timeout=3,
                               application_name='nervis-planner', autocommit=autocommit,
                               options='-c timezone=Asia/Seoul -c statement_timeout=5000 -c lock_timeout=3000',
                               row_factory=dict_row)


class PlannerStore:
    def __init__(self, settings):
        self.settings = settings

    @contextmanager
    def connection(self):
        try:
            with self.settings.connect() as conn:
                yield conn
        except psycopg.errors.UniqueViolation:
            raise PlannerError('duplicate_record', 409) from None
        except psycopg.IntegrityError:
            raise PlannerError('invalid_reference_or_fields', 422) from None
        except ValidationError:
            raise PlannerError('invalid_merged_fields', 422) from None
        except psycopg.Error:
            # Driver messages may contain SQL, credentials or user content.
            raise PlannerError('database_unavailable_or_schema_not_ready', 503) from None

    def status(self):
        with self.connection() as conn:
            names = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'").fetchall()
            required = {*TABLE_MODELS, 'api_requests'}
            if not required.issubset({r['table_name'] for r in names}):
                raise PlannerError('database_schema_not_ready', 503)
            return {'status': 'ok', 'timezone': conn.execute('SHOW timezone').fetchone()['TimeZone']}

    def _row(self, conn, table, entity_id, *, lock=False):
        if table not in TABLE_MODELS:
            raise ValueError('Unknown planner entity')
        query = sql.SQL('SELECT * FROM {} WHERE id=%s' + (' FOR UPDATE' if lock else '')).format(sql.Identifier(table))
        row = conn.execute(query, (entity_id,)).fetchone()
        if row is None:
            raise PlannerError('record_not_found', 404)
        return row

    def get(self, table, entity_id):
        with self.connection() as conn:
            return self._row(conn, table, entity_id)

    def list_courses(self, semester=None, limit=100, offset=0):
        with self.connection() as conn:
            return conn.execute('SELECT * FROM courses WHERE (%s::text IS NULL OR semester_name=%s) '
                                'ORDER BY starts_on DESC, id LIMIT %s OFFSET %s', (semester, semester, limit, offset)).fetchall()

    def list_meetings(self, course_id, limit=100, offset=0):
        with self.connection() as conn:
            self._row(conn, 'courses', course_id)
            return conn.execute('SELECT * FROM class_meetings WHERE course_id=%s ORDER BY weekday, starts_at, id LIMIT %s OFFSET %s',
                                (course_id, limit, offset)).fetchall()

    def list_tasks(self, *, status=None, planned_on=None, due_before=None, course_id=None, limit=100, offset=0):
        with self.connection() as conn:
            return conn.execute('SELECT * FROM tasks WHERE (%s::text IS NULL OR status=%s) '
                                'AND (%s::date IS NULL OR planned_on=%s) '
                                'AND (%s::date IS NULL OR due_on<=%s) '
                                'AND (%s::bigint IS NULL OR course_id=%s) '
                                'ORDER BY due_on NULLS LAST, planned_on NULLS LAST, id LIMIT %s OFFSET %s',
                                (status, status, planned_on, planned_on, due_before, due_before,
                                 course_id, course_id, limit, offset)).fetchall()

    def _insert(self, conn, table, values):
        columns = list(values)
        query = sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns)),
            sql.SQL(',').join(sql.Placeholder() for _ in columns))
        return conn.execute(query, [values[c] for c in columns]).fetchone()

    def _create_once(self, request_id, operation, payload, write):
        if not isinstance(request_id, UUID):
            raise PlannerError('request_uuid_required')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                           separators=(',', ':')).encode('utf-8')).hexdigest()
        with self.connection() as conn:
            fresh = conn.execute('INSERT INTO api_requests(request_id, operation, payload_hash) '
                                 'VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING request_id',
                                 (request_id, operation, digest)).fetchone()
            if not fresh:
                receipt = conn.execute('SELECT * FROM api_requests WHERE request_id=%s', (request_id,)).fetchone()
                if receipt['operation'] != operation or receipt['payload_hash'] != digest:
                    raise PlannerError('idempotency_key_conflict', 409)
                return receipt['response']
            response = jsonable_encoder(write(conn))
            conn.execute('UPDATE api_requests SET response=%s WHERE request_id=%s', (Jsonb(response), request_id))
            return response

    def create_course(self, body, request_id):
        return self._create_once(request_id, 'create_course', body.model_dump(mode='json'),
                                 lambda conn: self._insert(conn, 'courses', body.model_dump()))

    def create_meeting(self, course_id, body, request_id):
        return self._create_once(request_id, f'create_meeting:{course_id}', body.model_dump(mode='json'),
                                 lambda conn: self._insert(conn, 'class_meetings',
                                                          {'course_id': course_id, **body.model_dump()}))

    def create_task(self, body, request_id):
        return self._create_once(request_id, 'create_task', body.model_dump(mode='json'),
                                 lambda conn: self._insert(conn, 'tasks', body.model_dump()))

    def create_tasks(self, body, request_id):
        return self._create_once(request_id, 'create_tasks', body.model_dump(mode='json'),
                                 lambda conn: [self._insert(conn, 'tasks', item.model_dump()) for item in body.items])

    def update(self, table, entity_id, body):
        with self.connection() as conn:
            current = self._row(conn, table, entity_id, lock=True)
            changes = body.model_dump(exclude_unset=True)
            merged = {**current, **changes}
            model = TABLE_MODELS[table]
            model.model_validate({name: merged[name] for name in model.model_fields})
            if table == 'tasks' and 'status' in changes:
                changes['completed_at'] = (current['completed_at'] or datetime.now(timezone.utc)) if changes['status'] == 'done' else None
            query = sql.SQL('UPDATE {} SET {} WHERE id=%s RETURNING *').format(
                sql.Identifier(table), sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in changes))
            return conn.execute(query, [*changes.values(), entity_id]).fetchone()

    def delete(self, table, entity_id):
        with self.connection() as conn:
            self._row(conn, table, entity_id, lock=True)
            conn.execute(sql.SQL('DELETE FROM {} WHERE id=%s').format(sql.Identifier(table)), (entity_id,))

    def daily(self, day: date, location: str):
        with self.connection() as conn:
            classes = conn.execute('SELECT m.*, c.name AS course_name, c.semester_name FROM class_meetings m '
                                   'JOIN courses c ON c.id=m.course_id WHERE c.starts_on<=%s AND c.ends_on>=%s '
                                   'AND m.weekday=%s ORDER BY m.starts_at,m.id LIMIT 201',
                                   (day, day, day.isoweekday())).fetchall()
            tasks = conn.execute("SELECT * FROM tasks WHERE status<>'done' AND (planned_on<=%s OR due_on<=%s) "
                                 'ORDER BY due_on NULLS LAST, id LIMIT 201', (day, day)).fetchall()
            return {'date': day, 'timezone': 'Asia/Seoul', 'classes': classes[:200], 'tasks': tasks[:200],
                    'has_more_classes': len(classes) > 200, 'has_more_tasks': len(tasks) > 200,
                    'weather': {'status': 'not_connected', 'location': location}}
