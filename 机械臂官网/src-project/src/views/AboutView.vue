<template>
  <div class="about-view">
    <CompanySection />
    <AboutUs />
    <OurMission />
  </div>
</template>

<script setup>
import AboutUs from '@/components/AboutUs.vue'
import CompanySection from '@/components/CompanySection.vue'
import OurMission from '@/components/OurMission.vue'
</script>

<style scoped>
.about-view {
  background-color: #000;
}
</style>
