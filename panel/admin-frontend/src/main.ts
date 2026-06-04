import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import Tooltip from 'primevue/tooltip'
import 'primeicons/primeicons.css'
import router from './router'
import App from './App.vue'
import { i18n } from './i18n'

const app = createApp(App)

app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: { darkModeSelector: '.app-dark' },
  },
})
app.use(ConfirmationService)
app.use(ToastService)
app.use(router)
app.use(i18n)
app.directive('tooltip', Tooltip)
app.mount('#app')
