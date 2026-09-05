<template>
  <section class="hero-section" id="hero">
    <div class="container">
      <div class="row align-items-center">
        <div class="col-lg-6">
          <p class="lead">EASE FUTURE</p>
          <h1 class="display-4 fw-bold mb-4">智能理疗机器人 R1</h1>
          <button class="btn btn-outline-light btn-lg" @click="goToVideo">观看视频</button>
        </div>
        <!-- <div class="col-lg-6 mt-5 mt-lg-0">
          <div class="ratio ratio-16x9">
            <iframe
              src="https://www.youtube.com/embed/dQw4w9WgXcQ"
              title="公司介绍"
              allowfullscreen
            ></iframe>
          </div>
        </div> -->
      </div>
    </div>
  </section>
</template>

<script setup>
const goToVideo = () => {
  // 瞄点跳转
  window.location.href = '#video'
}
</script>

<style scoped>
.hero-section {
  background: url('https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/banner.png')
    center/cover no-repeat;
  color: white;
  padding: 100px 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
}
@media (max-width: 768px) {
  .hero-section {
    min-height: 50vh;
  }
}
@media (max-width: 640px) {
  .hero-section {
    min-height: 40vh;
  }
}
</style>
