<template>
  <footer class="bg-dark text-light py-5">
    <div class="container">
      <div class="row">
        <div class="col-lg-4 mb-4 mb-lg-0">
          <h5 class="mb-3"><i class="bi bi-building me-2"></i>公司名称</h5>
          <p>我们是一家专注于提供创新科技解决方案的公司，致力于帮助客户实现数字化转型。</p>
          <div class="d-flex gap-3">
            <a
              v-for="social in socialLinks"
              :key="social.name"
              :href="social.link"
              class="text-light fs-5"
            >
              <i :class="social.icon"></i>
            </a>
          </div>
        </div>
        <div class="col-lg-2 col-md-6 mb-4 mb-md-0">
          <h5 class="mb-3">快速链接</h5>
          <ul class="list-unstyled">
            <li v-for="link in quickLinks" :key="link.name" class="mb-2">
              <a :href="link.url" class="text-light text-decoration-none">{{ link.name }}</a>
            </li>
          </ul>
        </div>
        <div class="col-lg-3 col-md-6 mb-4 mb-md-0">
          <h5 class="mb-3">联系我们</h5>
          <ul class="list-unstyled">
            <li class="mb-2"><i class="bi bi-geo-alt me-2"></i>北京市朝阳区科技园区123号</li>
            <li class="mb-2"><i class="bi bi-telephone me-2"></i>+86 10 1234 5678</li>
            <li class="mb-2"><i class="bi bi-envelope me-2"></i>contact@company.com</li>
          </ul>
        </div>
        <div class="col-lg-3">
          <h5 class="mb-3">订阅我们的新闻</h5>
          <div class="input-group mb-3">
            <input type="email" class="form-control" placeholder="您的邮箱地址" />
            <button class="btn btn-primary" type="button">订阅</button>
          </div>
          <p class="small">订阅以获取最新产品更新和行业资讯</p>
        </div>
      </div>
      <hr class="my-4" />
      <div class="row align-items-center">
        <div class="col-md-6 text-center text-md-start">
          <p class="mb-0">&copy; 2023 公司名称. 保留所有权利.</p>
        </div>
        <div class="col-md-6 text-center text-md-end">
          <a href="#" class="text-light text-decoration-none me-3">隐私政策</a>
          <a href="#" class="text-light text-decoration-none">使用条款</a>
        </div>
      </div>
    </div>
  </footer>
</template>

<script>
export default {
  name: 'AppFooter',
  data() {
    return {
      socialLinks: [
        { name: 'Facebook', icon: 'bi bi-facebook', link: '#' },
        { name: 'Twitter', icon: 'bi bi-twitter', link: '#' },
        { name: 'LinkedIn', icon: 'bi bi-linkedin', link: '#' },
        { name: 'Instagram', icon: 'bi bi-instagram', link: '#' },
      ],
      quickLinks: [
        { name: '首页', url: '#home' },
        { name: '关于我们', url: '#about' },
        { name: '服务', url: '#services' },
        { name: '团队', url: '#team' },
        { name: '联系我们', url: '#contact' },
      ],
    }
  },
}
</script>
