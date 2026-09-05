<template>
  <section class="py-5" id="team">
    <div class="container">
      <div class="row mb-5">
        <div class="col text-center">
          <h2 class="display-5 fw-bold">我们的团队</h2>
          <p class="text-muted lead">经验丰富的专业团队</p>
        </div>
      </div>
      <div class="row g-4">
        <div class="col-md-6 col-lg-3" v-for="member in teamMembers" :key="member.name">
          <div class="card text-center h-100">
            <img :src="member.photo" class="card-img-top" :alt="member.name" />
            <div class="card-body">
              <h5 class="card-title">{{ member.name }}</h5>
              <p class="card-text text-muted">{{ member.position }}</p>
              <p class="card-text small">{{ member.bio }}</p>
              <div class="d-flex justify-content-center gap-2">
                <a
                  v-for="social in member.social"
                  :key="social.platform"
                  :href="social.link"
                  class="text-decoration-none"
                >
                  <i :class="social.icon" class="fs-5"></i>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
export default {
  name: 'TeamSection',
  data() {
    return {
      teamMembers: [
        {
          name: '张明',
          position: 'CEO/创始人',
          bio: '拥有15年互联网行业经验，专注于技术创新和业务发展。',
          photo:
            'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60',
          social: [
            { platform: 'linkedin', icon: 'bi bi-linkedin', link: '#' },
            { platform: 'twitter', icon: 'bi bi-twitter', link: '#' },
          ],
        },
        {
          name: '李华',
          position: '技术总监',
          bio: '全栈开发专家，主导多个大型项目的技术架构设计。',
          photo:
            'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60',
          social: [
            { platform: 'github', icon: 'bi bi-github', link: '#' },
            { platform: 'twitter', icon: 'bi bi-twitter', link: '#' },
          ],
        },
        // 更多团队成员...
      ],
    }
  },
}
</script>

<style scoped>
.card-img-top {
  height: 200px;
  object-fit: cover;
}
</style>
