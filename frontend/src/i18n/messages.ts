import en from './locales/en.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'
import zh from './locales/zh.json'

export const SUPPORTED_LOCALES = ['zh-CN', 'ja-JP', 'en-US', 'ko-KR'] as const

export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

export const DEFAULT_LOCALE: AppLocale = 'zh-CN'

export const messages = {
  'zh-CN': zh,
  'ja-JP': ja,
  'en-US': en,
  'ko-KR': ko,
}
