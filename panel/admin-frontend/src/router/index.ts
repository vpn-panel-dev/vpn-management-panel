import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import NodeSettingsView from '../views/NodeSettingsView.vue'
import NodesView from '../views/NodesView.vue'
import RemnawaveSettingsView from '../views/RemnawaveSettingsView.vue'
import UsersView from '../views/UsersView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/nodes' },
  { path: '/nodes', component: NodesView, meta: { requiresAuth: true } },
  { path: '/nodes/:id/settings', component: NodeSettingsView, meta: { requiresAuth: true } },
  { path: '/users', component: UsersView, meta: { requiresAuth: true } },
  { path: '/users/:id', component: UsersView, meta: { requiresAuth: true } },
  {
    path: '/integrations/remnawave',
    component: RemnawaveSettingsView,
    meta: { requiresAuth: true },
  },
  { path: '/login', component: LoginView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('token')) {
    return '/login'
  }
})

export default router
