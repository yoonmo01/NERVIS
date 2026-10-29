"""Local result narration when the model explanation could not be validated."""


def result_narration(results):
    lines = ['AI 설명을 준비하지 못해 조회 결과를 직접 안내합니다.']
    for result in results:
        tool, data = result['tool'], result['data']
        if tool == 'get_daily_briefing':
            lines.append(f"{data['date']} 브리핑입니다.")
            lines.extend(weather_lines(data.get('weather', {})))
            if data.get('calendar_status') == 'unavailable':
                lines.append('수업과 할 일은 조회하지 못했습니다.')
                continue
            classes = data.get('classes', [])
            lines.append(f'조회된 수업은 {len(classes)}개입니다.')
            lines.extend(f"{row['starts_at'][:5]}부터 {row['ends_at'][:5]}까지 {row['course_name']} 수업입니다." for row in classes[:3])
            if len(classes) > 3 or data.get('has_more_classes'):
                lines.append('추가 수업은 화면에서 확인해 주세요.')
            tasks = [row for row in data.get('tasks', []) if row.get('status') != 'done']
            for group, label in (('overdue', '기한 지난 일'), ('today', '해당 날짜 할 일'), ('remaining', '남은 할 일')):
                rows = [row for row in tasks if row.get('task_group', 'remaining') == group]
                if rows:
                    lines.append(f'{label}은 {len(rows)}개입니다.')
                    lines.extend(task_line(row) for row in rows[:3])
                    if len(rows) > 3:
                        lines.append('이 그룹의 나머지 항목은 화면에서 확인해 주세요.')
            if not tasks:
                lines.append('조회된 목록에는 미완료 할 일이 없습니다.')
            if data.get('has_more_tasks'):
                lines.append('조회 한도를 넘어 추가 할 일이 있을 수 있습니다.')
        elif tool == 'get_weather':
            lines.extend(weather_lines(data))
        elif tool == 'list_tasks':
            rows = data.get('items', [])
            lines.append(f'조회된 할 일은 {len(rows)}개입니다.')
            lines.extend(task_line(row) for row in rows[:6])
            if len(rows) > 6 or data.get('has_more'):
                lines.append('추가 항목은 화면에서 확인해 주세요.')
        elif tool in ('manage_tasks', 'register_courses'):
            lines.append(data.get('message', '처리 결과를 화면에서 확인해 주세요.'))
        else:
            lines.append('분석 결과는 받았습니다. 자세한 값과 계산 조건은 분석 화면에서 확인해 주세요.')
            break
    # Leave space for a complete notice rather than cutting a task title in the middle.
    kept = []
    for line in lines:
        if len(' '.join([*kept, line])) > 1800:
            kept.append('나머지 내용은 화면에서 확인해 주세요.')
            break
        kept.append(line)
    return ' '.join(kept)


def task_line(row):
    status = {'todo': '할 예정', 'in_progress': '진행 중', 'done': '완료'}.get(row.get('status'), '')
    parts = [row['title'], status]
    if row.get('planned_on'):
        parts.append(f"예정일 {row['planned_on']}")
    if row.get('due_on'):
        parts.append(f"마감 {row['due_on']} {row.get('due_time') or ''}".strip())
    return ', '.join(part for part in parts if part) + '.'


def weather_lines(weather):
    location = weather.get('location', '요청 지역')
    current = weather.get('current')
    lines = [f"{location} 관측 기온은 {current['temperature_c']}도입니다."] if isinstance(current, dict) and current.get('temperature_c') is not None else [f'{location} 현재 관측 기온 정보는 없습니다. 날씨 조회 상태와 예보는 화면에서 확인해 주세요.']
    daily = weather.get('daily') or {}
    for name, label in (('low_c', '최저'), ('high_c', '최고')):
        if daily.get(name) is not None:
            lines.append(f"해당 날짜 예보 {label} 기온은 {daily[name]}도입니다.")
    return lines
