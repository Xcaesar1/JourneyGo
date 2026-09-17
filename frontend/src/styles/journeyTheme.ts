import { computed } from 'vue'

export const journeyThemeName = 'outdoor'
export const journeyPalettes = {
  outdoor: {
    bg: '#f5f2e9', surface: '#fffef8', soft: '#e5ebdf', accent: '#315b45', strong: '#244735',
    text: '#263b30', muted: '#5d6b5c', border: '#d4d8c8', gold: '#c8a45c',
    heading: "Georgia, 'Noto Serif SC Variable', 'Songti SC', serif",
    shadow: '0 4px 18px rgb(38 59 48 / 4%)',
    categories: ['#315b45', '#47654b', '#496d38', '#786334', '#8c5440', '#526a68', '#6b603b', '#5d6b5c'],
    weather: ['#d4dccd', '#f3f1e8', '#dce4d5', '#deded1', '#e7e9dc', '#eee5c9'],
    routes: { driving: '#315b45', walking: '#786334', straight: '#5d6b5c' },
  },
}
export const journeyPalette = computed(() => journeyPalettes.outdoor)
export const journeyVariables = computed(() => {
  const p = journeyPalette.value
  return { '--jg-bg': p.bg, '--jg-surface': p.surface, '--jg-soft': p.soft,
    '--jg-accent': p.accent, '--jg-accent-strong': p.strong, '--jg-text': p.text,
    '--jg-muted': p.muted, '--jg-border': p.border, '--jg-gold': p.gold,
    '--jg-heading': p.heading, '--jg-shadow': p.shadow }
})
export const journeyTheme = computed(() => ({
  components: { DatePicker: { cellWidth: 44, cellHeight: 44 }, Select: { optionHeight: 44 } },
  token: {
    colorPrimary: journeyPalette.value.accent, colorInfo: journeyPalette.value.accent, colorSuccess: '#22724f',
    colorWarning: '#8b590d', colorError: '#b13d42', colorText: journeyPalette.value.text,
    colorTextSecondary: journeyPalette.value.muted, colorBgContainer: journeyPalette.value.surface,
    colorBgElevated: journeyPalette.value.surface, colorBorder: journeyPalette.value.border,
    colorFillSecondary: journeyPalette.value.soft, borderRadius: 12, controlHeight: 44,
    fontSize: 16, fontFamily: "'Nunito Sans', 'Noto Sans SC Variable', 'Microsoft YaHei', sans-serif",
  },
}))
