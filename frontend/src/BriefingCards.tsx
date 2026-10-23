import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type { Briefing } from './briefing.ts'
import { briefingTimeline } from './briefing.ts'
import type { BriefingStage } from './briefing.ts'
import { weatherMessage, weatherTime } from './weather.ts'

export default function BriefingCards({ value, reduced, onReady }: { value: Briefing; reduced: boolean; onReady: () => void }) {
  const kinds = value.weatherOnly ? ['weather'] : ['weather', 'classes', 'tasks']
  const [stage, setStage] = useState<BriefingStage>(reduced ? 'docked' : 'weather')
  const [heights, setHeights] = useState<number[]>([])
  const nodes = useRef<(HTMLElement | null)[]>([])
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])
  useEffect(() => {
    timers.current.forEach(clearTimeout)
    if (reduced) setStage('docked')
    else {
      setStage('weather')
      timers.current = briefingTimeline(value.weatherOnly).slice(1).map(step => setTimeout(() => setStage(step.phase), step.at))
    }
    return () => timers.current.forEach(clearTimeout)
  }, [reduced, value.weatherOnly])
  useEffect(() => { if (stage === 'docked') onReady() }, [stage, onReady])
  useEffect(() => {
    const measure = () => {
      const next = nodes.current.map(node => node?.offsetHeight ?? 0)
      setHeights(previous => next.every((height, i) => height === previous[i]) ? previous : next)
    }
    const observer = new ResizeObserver(measure)
    nodes.current.forEach(node => { if (node) observer.observe(node) })
    measure()
    return () => observer.disconnect()
  }, [value.weatherOnly])
  const skip = () => {
    timers.current.forEach(clearTimeout)
    setStage('docking')
    timers.current = [setTimeout(() => setStage('docked'), 1000)]
  }
  const w = value.weather
  const isToday = value.date === new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  return <aside className={`briefing-cards stage-${stage}`} aria-label="오늘 브리핑 카드" data-briefing-stage={stage}>
    <div className="briefing-caption">{value.preview ? '더미 미리보기 · 실제 일정 아님' : `${value.date} · ${value.weatherOnly ? '날씨' : '브리핑'}`}</div>
    {stage !== 'docked' && <button className="briefing-skip" disabled={stage === 'docking'} onClick={skip}>오른쪽에 정리 ↗</button>}
    {kinds.map((kind, index) => {
      const hidden = (stage === 'weather' && index > 0) || (stage === 'classes' && index > 1)
      const focused = (stage === 'weather' && index === 0) || (stage === 'classes' && index === 1) || (stage === 'tasks' && index === 2)
      const slot = kind === 'weather' && stage !== 'weather' ? -1 : kind === 'classes' && stage !== 'weather' && stage !== 'classes' ? 1 : 0
      const dockTop = 25 + heights.slice(0, index).reduce((total, height) => total + height + 12, 0)
      return <section key={kind} ref={node => { nodes.current[index] = node }} inert={hidden} aria-hidden={hidden}
        className={`briefing-card card-${kind}${hidden ? ' is-hidden' : ''}${focused ? ' is-focused' : ''}`}
        style={{ '--stage-x': `calc(50% + ${slot} * var(--stage-step))`, '--dock-top': `${dockTop}px` } as CSSProperties}>
      {kind === 'weather' && <><span className="briefing-eyebrow">WEATHER</span><h2>{w.location} 날씨</h2>
        {w.current ? <><strong className="briefing-temperature">{w.current.temperature_c}℃</strong><p>습도 {w.current.humidity_pct ?? '—'}% · 강수 {w.current.precipitation ?? '정보 없음'}</p></> : w.hourly[0] ? <p>{w.hourly[0].temperature_c ?? '—'}℃ · {w.hourly[0].sky ?? '예보'} · 강수확률 {w.hourly[0].rain_probability_pct ?? '—'}%</p> : null}
        {weatherMessage(w.status) && <p>{weatherMessage(w.status)}</p>}
        <small>{value.preview ? '날씨도 연출용 더미입니다.' : `${w.source ?? '기상청'} · ${weatherTime(w.current?.observed_at ?? w.fetched_at)} ${w.current ? '관측' : '조회'}`}</small></>}
      {kind === 'classes' && <><span className="briefing-eyebrow">CLASSES</span><h2>{isToday ? '오늘 수업' : '수업 일정'}</h2>
        {value.calendar_status === 'unavailable' ? <p>수업 목록을 조회하지 못했습니다.</p> : value.classes.length ? <ul>{value.classes.map((row, i) => <li key={i}><time>{row.starts_at.slice(0, 5)}–{row.ends_at.slice(0, 5)}</time><strong>{row.course_name}</strong>{row.location && <small>{row.location}</small>}</li>)}</ul> : <p>해당 날짜에 등록된 수업이 없습니다.</p>}
        {value.has_more_classes && <small>추가 수업이 있습니다.</small>}</>}
      {kind === 'tasks' && <><span className="briefing-eyebrow">TO DO</span><h2>해야 할 일</h2>
        {value.calendar_status === 'unavailable' ? <p>할 일 목록을 조회하지 못했습니다.</p> : value.tasks.length ? <ul>{value.tasks.map((row, i) => <li key={i}><strong>{row.title}</strong><small>{row.status === 'in_progress' ? '진행 중' : '할 예정'}{row.due_on ? ` · ${row.due_on}${row.due_time ? ` ${row.due_time.slice(0, 5)}` : ''} 마감` : ''}</small></li>)}</ul> : <p>해당 날짜까지 예정·마감인 미완료 할 일이 없습니다.</p>}
        {value.has_more_tasks && <small>추가 할 일이 있습니다.</small>}</>}
    </section>})}
  </aside>
}
