import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import App from './App.vue'
import UserPage from './UserPage.vue'

const routes: RouteRecordRaw[] = [{ path: '/:userId', component: UserPage }]

const router = createRouter({
  history: createWebHistory('/u/'),
  routes,
})

createApp(App).use(router).mount('#app')
