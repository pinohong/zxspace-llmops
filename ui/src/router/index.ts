import { createRouter, createWebHistory } from 'vue-router'
// import DefaultView import {  } from "module";
import DefaultLayout from "@/view/layouts/DefaultLayout.vue";
import BlankLayout from "@/view/layouts/BlankLayout.vue";
import auth from '@/utils/auth'
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // {
    //   path:"/home",
    //   name:"home",
    //   component:HomeView
    // }

    {
      path: "/",
      component: DefaultLayout,
      children: [
        {
          path: "",
          redirect: "home"
        },
        {
          path: "home",
          name: "pages-home",
          component: () => import("@/view/pages/HomeView.vue")
        },
        {
          path: 'space',
          component: () => import("@/view/space/SpaceLayouView.vue"),
          children: [

            {
              path: 'apps',
              name: 'space-apps-list',
              component: () => import('@/view/space/apps/ListView.vue')
            },
            {
              path: 'tools',
              name: 'space-tools-list',
              component: () => import('@/view/space/tools/ListView.vue'),
            },
            {
              path: 'workflows',
              name: 'space-workflows-list',
              component: () => import('@/view/space/workflows/ListView.vue'),
            },
            {
              path: 'datasets',
              name: 'space-datasets-list',
              component: () => import('@/view/space/datasets/ListView.vue'),
            }
          ]
        },
        {
          path: "store/tools",
          name: "store-tools-list",
          component: () => import('@/view/store/tools/ListView.vue')
        },
        {
          path: 'space/datasets/:dataset_id/documents',
          name: 'space-datasets-documents-list',
          component: () => import("@/view/space/datasets/documents/ListVIew.vue")
        },
        {
          path: 'space/datasets/:dataset_id/documents/create',
          name: 'space-datasets-documents-create',
          component: () => import('@/view/space/datasets/documents/CreateView.vue'),
        },
        {
          path: 'space/datasets/:dataset_id/documents/:document_id/segments',
          name: 'space-datasets-documents-segments-list',
          component: () => import('@/view/space/datasets/documents/segments/ListView.vue')
        },
        {
          path: 'store/apps',
          name: 'store-apps-list',
          component: () => import('@/view/store/apps/ListView.vue'),
        },
        {
          path: "openapi",
          component: () => import('@/view/openapi/OpenAPILayoutView.vue'),
          children:[
            {
              path: '',
              name: 'openapi-index',
              component: () => import('@/view/openapi/IndexView.vue'),
            },
            {
              path: 'api-keys',
              name: 'openapi-api-keys-list',
              component: () => import('@/view/openapi/api-keys/ListView.vue'),
            }
          ]
        },
      ]
    },
    {
      path: "/",
      component: BlankLayout,
      children: [
        {
          path: "auth/login",
          name: "auth-login",
          component: () => import("@/view/auth/LoginView.vue")
        },
        {
          path:"auth/authorize/:provider_name",
          name: 'auth-authorize',
          component: () => import('@/view/auth/AuthorizeView.vue'),
        },
        {
          path: 'space/workflows/:workflow_id',
          name: 'space-workflows-detail',
          component: () => import('@/view/space/workflows/DetailView.vue'),
        },
        {
          path: 'space/apps',
          component: () => import('@/view/space/apps/AppLayoutView.vue'),
          children: [
            {
              path: ':app_id',
              name: 'space-apps-detail',
              component: () => import('@/view/space/apps/DetailView.vue'),
            },
            {
              path: ':app_id/published',
              name: 'space-apps-published',
              component: () => import('@/view/space/apps/PublishedView.vue'),
            },
            {
              path: ':app_id/analysis',
              name: 'space-apps-analysis',
              component: () => import('@/view/space/apps/AnalysisView.vue'),
            },
          ],
        },
        {
          path: 'chat/:token',
          name: 'chat-index',
          component: () => import('@/view/chat/IndexView.vue'),
        },
        {
          path: '/errors/404',
          name: 'errors-not-found',
          component: () => import('@/view/errors/NotFoundView.vue'),
        },
        {
          path: '/errors/403',
          name: 'errors-forbidden',
          component: () => import('@/view/errors/ForbiddenView.vue'),
        },
        {
          // 兜底路由：所有未匹配到已定义路由的路径，统一跳转到404页面
          path: '/:pathMatch(.*)*',
          name: 'errors-not-found-fallback',
          redirect: '/errors/404',
        }
      ]
    }
  ],
})

router.beforeEach(async (to) => {
  if (!auth.isLogin() && !['auth-login', 'auth-authorize'].includes(to.name as string)) {
    return { path: '/auth/login' }
  }
})

export default router
