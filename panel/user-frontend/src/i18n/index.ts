import { createI18n } from 'vue-i18n'
import ru from '../locales/ru.json'
import en from '../locales/en.json'
import zh from '../locales/zh.json'

const messages = { ru, en, zh }

function getInitialLocale(): 'ru' | 'en' | 'zh' {
  const stored = localStorage.getItem('amnezia-locale')
  if (stored && ['ru', 'en', 'zh'].includes(stored)) return stored as 'ru' | 'en' | 'zh'
  const browser = navigator.language.slice(0, 2)
  if (['ru', 'en', 'zh'].includes(browser)) return browser as 'ru' | 'en' | 'zh'
  return 'ru'
}

export const i18n = createI18n({
  legacy: false,
  locale: getInitialLocale(),
  fallbackLocale: 'ru',
  messages,
})

export function setLocale(locale: string) {
  if (['ru', 'en', 'zh'].includes(locale)) {
    localStorage.setItem('amnezia-locale', locale)
    i18n.global.locale.value = locale as 'ru' | 'en' | 'zh'
  }
}
