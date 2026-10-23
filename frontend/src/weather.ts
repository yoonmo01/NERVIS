export interface Weather {
  status: string; location: string; date: string; cached: boolean; fetched_at: string | null;
  source: string; supported_locations: string[];
  current: null | { observed_at: string; temperature_c: number; humidity_pct: number | null; precipitation: string | null };
  hourly: { at: string; temperature_c: number | null; rain_probability_pct: number | null; sky: string | null }[];
}

export function weatherMessage(status: string) {
  return ({ not_configured: '서버에 기상청 인증키를 설정해 주세요.', unknown_location: '지원하는 지역을 선택해 주세요.',
    date_unavailable: '조회 가능한 예보 기간 밖입니다.', partial: '일부 날씨만 조회했습니다.',
    unavailable: '날씨를 가져오지 못했습니다. 잠시 후 다시 조회해 주세요.' } as Record<string, string>)[status] ?? ''
}

export function weatherTime(value: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return '—'
  return new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value))
}
