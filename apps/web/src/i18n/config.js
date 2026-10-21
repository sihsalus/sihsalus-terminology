import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import moment from 'moment';
import 'moment/locale/es';
import 'moment/locale/zh-cn';
import en from './locales/en/translations.json'
import es from './locales/es/translations.json'
import zh from './locales/zh/translations.json'

const dateLocales = { en: 'en', es: 'es', zh: 'zh-cn' };
i18n.on('languageChanged', language => {
  moment.locale(dateLocales[language.split('-')[0]] || 'en');
  if(typeof document !== 'undefined') document.documentElement.lang = language;
});

i18n.use(initReactI18next).init({
  fallbackLng: 'en',
  lng: 'es',
  resources: {
    en: {
      translations: en
    },
    es: {
      translations: es
    },
    zh: {
      translations: zh
    }
  },
  ns: ['translations'],
  defaultNS: 'translations'
});

i18n.languages = ['en', 'es', 'zh'];

export default i18n;
