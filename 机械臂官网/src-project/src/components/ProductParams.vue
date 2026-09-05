<template>
  <div class="row justify-content-center mb-5 gy-4">
    <div class="card w-100 border-0 p-4">
      <!-- 左侧垂直标题 -->
      <div class="d-flex align-items-start h-100 gap-4">
        <div
          class="bg-gray-300 h-100 p-4 d-flex flex-column justify-content-center align-items-center text-center"
          style="width: 80px; font-size: 1.2rem; line-height: 1.4"
        >
          产品参数
        </div>

        <!-- 右侧参数内容 -->
        <table class="table table-borderless w-100 mb-0 ml-4">
          <tbody>
            <tr
              v-for="(item, index) in params"
              :key="index"
              :class="{ 'tb-light': index % 2 === 0, 'tb-dark': index % 2 === 1 }"
            >
              <td class="text-center fw-bold">{{ item.name }}</td>
              <td class="text-center">{{ item.x }}</td>
              <td class="text-center">{{ item.y }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
// 接收外部传入的参数列表
defineProps({
  params: {
    type: Array,
    required: true,
    default: () => [],
  },
})
</script>

<style scoped>
.bg-gray-300 {
  border-radius: 15px;
  background-color: #3b3b3b4d;
}
.table td,
.table th {
  background-color: transparent;
}
/* 表格单元格背景色 */
.tb-light {
  background: #3b3b3b4d;
}

.tb-dark {
  /* background: #f8f9fa; */
}
/* 加粗标题行 */
.table thead th {
  font-weight: bold;
  color: #333;
}
/* 单元格内文字对齐 */
.table td {
  padding: 1.5rem;
  vertical-align: middle;
}

/* 第一个 td：左上 + 左下 圆角 */
.table tbody tr td:first-child {
  border-top-left-radius: 15px;
  border-bottom-left-radius: 15px;
}

/* 最后一个 td：右上 + 右下 圆角 */
.table tbody tr td:last-child {
  border-top-right-radius: 15px;
  border-bottom-right-radius: 15px;
}
</style>
