// Match provider descriptions and retained translated records without changing source data.
const conditions = [
  ['Clear sky', '晴', '快晴', '맑음', 'clear|sunny'],
  ['Mainly clear', '晴间多云', 'おおむね晴れ', '대체로 맑음', 'mostly clear|mostly sunny'],
  ['Partly cloudy', '多云', '晴れ時々曇り', '구름 조금', 'partially cloudy'],
  ['Overcast', '阴', '曇り', '흐림', 'cloudy'],
  ['Fog', '雾', '霧', '안개', 'foggy'],
  ['Depositing rime fog', '雾凇', '着氷性の霧', '착빙 안개', 'rime fog'],
  ['Light drizzle', '小毛毛雨', '弱い霧雨', '약한 이슬비', 'drizzle: light'],
  ['Moderate drizzle', '中等毛毛雨', '霧雨', '보통 이슬비', 'drizzle: moderate'],
  ['Dense drizzle', '浓毛毛雨', '強い霧雨', '강한 이슬비', 'heavy drizzle|drizzle: dense'],
  ['Drizzle', '毛毛雨', '細雨', '이슬비', ''],
  ['Light freezing drizzle', '轻微冻毛毛雨', '弱い着氷性の霧雨', '약한 어는 이슬비', ''],
  ['Dense freezing drizzle', '强冻毛毛雨', '強い着氷性の霧雨', '강한 어는 이슬비', ''],
  ['Light rain', '小雨', '小雨', '약한 비', 'slight rain'],
  ['Moderate rain', '中雨', '雨', '보통 비', ''],
  ['Heavy rain', '大雨', '大雨', '강한 비', 'heavy rain intensity'],
  ['Rain', '雨', '降雨', '비', 'rainy'],
  ['Light freezing rain', '轻微冻雨', '弱い着氷性の雨', '약한 어는 비', ''],
  ['Heavy freezing rain', '强冻雨', '強い着氷性の雨', '강한 어는 비', ''],
  ['Freezing rain', '冻雨', '着氷性の雨', '어는 비', ''],
  ['Slight snow fall', '小雪', '小雪', '약한 눈', 'light snowfall|light snow|slight snowfall'],
  ['Moderate snow fall', '中雪', '雪', '보통 눈', 'moderate snowfall|moderate snow'],
  ['Heavy snow fall', '大雪', '大雪', '강한 눈', 'heavy snowfall|heavy snow'],
  ['Snow grains', '米雪', '霧雪', '싸락눈', ''],
  ['Snow', '雪', '降雪', '눈', 'snowy'],
  ['Slight rain showers', '小阵雨', '弱いにわか雨', '약한 소나기', 'light rain showers|light showers'],
  ['Moderate rain showers', '中等阵雨', 'にわか雨', '보통 소나기', 'moderate showers'],
  ['Violent rain showers', '强阵雨', '激しいにわか雨', '강한 소나기', 'heavy rain showers|heavy showers'],
  ['Rain showers', '阵雨', '断続的な雨', '소나기', 'showers'],
  ['Slight snow showers', '小阵雪', '弱いにわか雪', '약한 눈 소나기', 'light snow showers'],
  ['Heavy snow showers', '强阵雪', '強いにわか雪', '강한 눈 소나기', ''],
  ['Thunderstorm', '雷阵雨', '雷雨', '뇌우', 'thunderstorm: slight or moderate|slight or moderate thunderstorm'],
  ['Thunderstorm with slight hail', '雷阵雨伴小冰雹', '小さなひょうを伴う雷雨', '작은 우박을 동반한 뇌우', 'thunderstorm with light hail'],
  ['Thunderstorm with heavy hail', '雷阵雨伴大冰雹', '大きなひょうを伴う雷雨', '큰 우박을 동반한 뇌우', ''],
  ['Haze', '霾', '煙霧', '연무', ''],
  ['Sleet', '雨夹雪', 'みぞれ', '진눈깨비', ''],
] as const

const normalize = (text: string) => text.trim().toLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ')

export function weatherText(raw: string | null | undefined, locale: string): string {
  if (!raw?.trim()) return '--'
  const language = locale.split('-')[0]
  const index = { en: 0, zh: 1, ja: 2, ko: 3 }[language] ?? 0
  const value = normalize(raw)
  const match = conditions.find(row => [...row.slice(0, 4), ...row[4].split('|')].some(alias => normalize(alias) === value))
  return match?.[index] ?? ['Unavailable', '暂无描述', '説明なし', '설명 없음'][index]!
}
