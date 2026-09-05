<template>
  <section class="our-section">
    <div class="container">
      <div class="row align-items-center justify-content-center g-5">
        <div class="col-md-6">
          <div class="d-flex text-white fw-bold gap-5 align-items-center">
            <svg
              t="1759132625845"
              class="icon"
              viewBox="0 0 1024 1024"
              version="1.1"
              xmlns="http://www.w3.org/2000/svg"
              p-id="17583"
              width="100"
              height="100"
            >
              <path
                d="M512 108.089c205.141 0 375.467 78.62 375.467 191.715 0 5.234-0.399 10.411-1.138 15.588a34.19 34.19 0 0 1 0.683 3.243l0.455 5.518v395.719c0 113.038-170.326 191.716-375.467 191.716-193.252 0-356.01-69.917-373.93-174.536l-1.138-8.76-0.399-8.42v-395.72c0-2.957 0.399-5.859 1.138-8.59a115.712 115.712 0 0 1-1.138-15.814c0-113.039 170.326-191.66 375.467-191.66z m307.314 509.099c-68.324 49.095-181.248 78.79-307.314 78.79s-238.933-29.695-307.257-78.79v101.091l0.228 5.29C210.546 783.873 344.633 843.265 512 843.265c166.684 0 298.951-58.71 306.802-117.874l0.398-5.518zM512 176.356c-171.861 0-307.2 62.464-307.2 123.448 0 60.872 135.339 123.336 307.2 123.336 51.883 0 95.004-2.845 146.66-13.483a34.133 34.133 0 0 1 13.767 66.901c-32.54 6.713-65.423 10.81-98.418 13.028-22.528 1.479-39.083 1.82-62.009 1.82-126.009 0-238.933-29.639-307.2-78.734v92.16l0.398 5.006c7.566 57.287 131.982 114.233 291.271 117.76l15.531 0.114c171.861 0 307.2-62.464 307.2-123.449v-91.705l-9.842 6.827a34.133 34.133 0 0 1-43.804-5.575l-3.414-4.38a34.133 34.133 0 0 1 9.956-47.218c20.764-13.54 34.873-27.99 41.927-41.984a44.942 44.942 0 0 0 5.177-20.424c0-60.984-135.339-123.448-307.2-123.448z"
                fill="#ffffff"
                p-id="17584"
              ></path>
            </svg>
            <div>
              <div class="fs-4 mission-text">OUR MISSION</div>
              <div class="fs-3">我们的使命</div>
              <div class="mission-desc">具身智能体服务世界</div>
            </div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="d-flex text-white fw-bold gap-5 align-items-center">
            <svg
              t="1759133933830"
              class="icon"
              viewBox="0 0 1024 1024"
              version="1.1"
              xmlns="http://www.w3.org/2000/svg"
              p-id="23346"
              id="mx_n_1759133933831"
              width="100"
              height="100"
            >
              <path
                d="M64.2 63.9v895.7h895.7V63.9H64.2z m814.3 814.2H732.3V732h146.1v146.1zM650.9 650.6v227.6H145.6V145.3h732.8v505.3H650.9z"
                fill="#ffffff"
                p-id="23347"
              ></path>
            </svg>
            <div>
              <div class="fs-4 mission-text">OUR VISION</div>
              <div class="fs-3">我们的愿景</div>
              <div class="mission-desc">部署100亿台AI机器人</div>
              <div class="mission-desc" style="margin-top: 5px">服务100亿全球人口</div>
            </div>
          </div>
        </div>
      </div>
      <!-- 分割线 -->
      <div class="row" style="margin-top: 10em">
        <div class="col-12 divider"></div>
      </div>
      <!-- 投资人 -->
      <div class="row align-items-center justify-content-center p-5">
        <div class="row">
          <div class="col-12 w-100 text-center">
            <div class="display-5 text-white mt-3 fw-bold">我们的投资人</div>
          </div>
          <div class="col-12 w-100 mt-5">
            <div class="text-white mt-3 custom-line-height">
              今年2月，星海图成功完成新一轮A轮融资，总融资额近3亿元人民币。本轮融资由蚂蚁集团独家领投，高瓴创投、IDG资本、北京机器人产业基金、百度风投、同歌创投等一众老股东持续加码。短短一年内，星海图已成功完成四轮融资，累计融资额近1亿美元。
            </div>
          </div>
          <!-- 投资人Logo列表 -->
          <div class="row justify-content-center mt-5">
            <!-- 第一行：5个Logo -->
            <div class="col-12 d-flex flex-wrap justify-content-center gap-3">
              <div
                class="logo-card col-5 col-md-5 col-lg-2 flex-grow-1"
                v-for="(logo, index) in investorLogos"
                :key="index"
              >
                <img :src="logo.src" :alt="logo.name" class="logo-img" />
              </div>
            </div>

            <!-- 第二行：6个Logo -->
            <div class="col-12 d-flex flex-wrap justify-content-center gap-3 mt-4">
              <div
                class="logo-card col-3 col-md-3 col-lg-1 flex-grow-1"
                v-for="(logo, index) in investorLogos2"
                :key="index"
              >
                <img :src="logo.src" :alt="logo.name" class="logo-img" />
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- 分割线 -->
      <div class="row" style="margin-top: 10em">
        <div class="col-12 divider"></div>
      </div>
      <!-- 客户 -->
      <div class="row align-items-center justify-content-center p-5">
        <div class="row">
          <div class="col-12 w-100 text-center">
            <div class="display-5 text-white mt-3 fw-bold">我们的客户</div>
          </div>
          <div class="col-12 w-100 mt-5">
            <div class="text-white mt-3 custom-line-height">
              星海图已成功服务四十多家客户，主要满足大型科技企业、创业公司、高校、科研机构/国家实验室四类客户群体，在算法开发、场景落地、数据采集三个层面的需求。
            </div>
          </div>
          <!-- 投资人Logo列表 -->
          <div class="row justify-content-center mt-5">
            <!-- 第一行：5个Logo -->
            <div class="col-6 d-flex flex-wrap justify-content-center gap-3">
              <div
                class="logo-card col-5 col-md-5 col-lg-2 flex-grow-1"
                v-for="(logo, index) in investorLogos"
                :key="index"
              >
                <img :src="logo.src" :alt="logo.name" class="logo-img" />
              </div>
            </div>

            <!-- 第二行：6个Logo -->
            <div class="col-6 d-flex flex-wrap justify-content-center gap-3 mt-4">
              <div
                class="logo-card col-3 col-md-3 col-lg-1 flex-grow-1"
                v-for="(logo, index) in investorLogos2"
                :key="index"
              >
                <img :src="logo.src" :alt="logo.name" class="logo-img" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
const investorLogos = [
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_1.png&w=384&q=75',
    name: '蚂蚁集团',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_2.png&w=384&q=75',
    name: '高瓴创投',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_3.png&w=384&q=75',
    name: '米哈游',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_4.png&w=384&q=75',
    name: '百度风投',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_5.png&w=384&q=75',
    name: '北京机器人产业发展投资基金',
  },
]

const investorLogos2 = [
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_6.png&w=384&q=75',
    name: 'SEE FUND',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_7.png&w=384&q=75',
    name: '无锡创业投资集团有限公司',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_8.png&w=384&q=75',
    name: '七熹投资',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_9.png&w=384&q=75',
    name: '同歌创投',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_10.png&w=384&q=75',
    name: '趣加科技',
  },
  {
    src: 'https://galaxea-ai.com/_next/image?url=%2Fimages%2Fabout%2Ftz_11.png&w=384&q=75',
    name: '首钢基金',
  },
]
</script>

<style scoped>
.our-section {
  display: flex;
  align-items: center;
  margin-top: 10em;
}
.container {
  min-height: 80vh;
}
.custom-line-height {
  line-height: 2.5; /* 自定义行高 */
}
.mission-text {
  color: #f4977b;
  font-weight: normal;
}
.mission-desc {
  font-size: 1.5em;
  font-weight: normal;
  margin-top: 2em;
}
.divider {
  border-top: 1px solid #1e2939;
}
.logo-card {
  background-color: #f8f9fa;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
  padding: 1rem; /* 可选：增加内边距 */
}

.logo-card:hover {
  transform: translateY(-5px);
}

.logo-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
</style>
