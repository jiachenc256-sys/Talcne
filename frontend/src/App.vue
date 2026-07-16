<template>
  <div id="app">
    <header class="topbar">
      <div class="brand">
        <span class="seal">弾</span>
        <div class="brand-text">
          <h1>弹词文字识别助手</h1>
          <p class="subtitle">上传刻本图片 · 自动识别 · 逐字校对</p>
        </div>
      </div>
      <span class="stage-tag">MVP · 第一阶段</span>
    </header>

    <section class="toolbar">
      <label class="btn btn-ghost">
        选择图片
        <input type="file" accept="image/*" hidden @change="handleFileUpload" />
      </label>
      <button
        class="btn btn-primary"
        :disabled="!uploadedFile || isProcessing"
        @click="recognizeText"
      >
        {{ isProcessing ? '识别中…' : '开始识别文字' }}
      </button>
      <span v-if="fileName" class="file-name">{{ fileName }}</span>
      <span v-if="errorMsg" class="error-msg">{{ errorMsg }}</span>
    </section>

    <section v-if="imageUrl" class="workspace">
      <div class="panel image-panel">
        <p class="panel-label">刻本原图</p>
        <div class="image-wrapper" ref="wrapperRef">
          <img
            ref="imgRef"
            class="source-image"
            :src="imageUrl"
            alt="弹词刻本原图"
            @load="onImageLoad"
          />
          <div
            v-for="(block, idx) in blocks"
            :key="'box-' + idx"
            class="overlay-box"
            :class="{ active: hoverIndex === idx, low: block.confidence < 0.9 }"
            :style="overlayStyle(block)"
            @mouseenter="hoverIndex = idx"
            @mouseleave="hoverIndex = null"
          ></div>
        </div>
      </div>

      <div class="spine"></div>

      <div class="panel text-panel">
        <p class="panel-label">
          识别结果
          <span class="hint">
            <i class="dot dot-low"></i>置信度较低，建议重点校对
          </span>
        </p>

        <div v-if="blocks.length" class="text-blocks">
          <span
            v-for="(block, idx) in blocks"
            :key="'chip-' + idx"
            class="text-chip"
            :class="{ active: hoverIndex === idx, low: block.confidence < 0.9 }"
            :title="`置信度 ${(block.confidence * 100).toFixed(1)}%`"
            @mouseenter="hoverIndex = idx"
            @mouseleave="hoverIndex = null"
            >{{ block.text }}</span
          >
        </div>
        <p v-else class="placeholder">点击上方「开始识别文字」查看结果</p>

        <p class="panel-label secondary">可编辑全文</p>
        <textarea
          class="edit-area"
          v-model="editableText"
          placeholder="识别结果将出现在这里，你可以直接修改校对…"
          rows="10"
        ></textarea>
      </div>
    </section>

    <section v-else class="empty-state">
      <span class="seal seal-big">弾</span>
      <p>请选择一张清晰的弹词刻本图片开始</p>
    </section>
  </div>
</template>

<script>
// 后端接口地址：本地开发默认指向 FastAPI 的 8000 端口
// 部署到 Vercel 后，可在项目的环境变量里设置 VITE_API_BASE 指向线上后端地址（如 Render 域名）
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default {
  name: 'App',
  data() {
    return {
      uploadedFile: null,
      fileName: '',
      imageUrl: null,
      blocks: [],
      editableText: '',
      isProcessing: false,
      errorMsg: '',
      hoverIndex: null,
      naturalSize: { width: 0, height: 0 },
      displaySize: { width: 0, height: 0 },
    }
  },
  methods: {
    handleFileUpload(event) {
      const file = event.target.files[0]
      if (!file) return
      this.uploadedFile = file
      this.fileName = file.name
      this.imageUrl = URL.createObjectURL(file)
      this.blocks = []
      this.editableText = ''
      this.errorMsg = ''
    },
    onImageLoad() {
      const img = this.$refs.imgRef
      if (!img) return
      this.naturalSize = { width: img.naturalWidth, height: img.naturalHeight }
      this.displaySize = { width: img.clientWidth, height: img.clientHeight }
    },
    overlayStyle(block) {
      const loc = block.location || {}
      const scaleX = this.naturalSize.width ? this.displaySize.width / this.naturalSize.width : 1
      const scaleY = this.naturalSize.height ? this.displaySize.height / this.naturalSize.height : 1
      return {
        left: (loc.left || 0) * scaleX + 'px',
        top: (loc.top || 0) * scaleY + 'px',
        width: (loc.width || 0) * scaleX + 'px',
        height: (loc.height || 0) * scaleY + 'px',
      }
    },
    async recognizeText() {
      if (!this.uploadedFile) return
      this.isProcessing = true
      this.errorMsg = ''

      const formData = new FormData()
      formData.append('file', this.uploadedFile)

      try {
        const response = await fetch(`${API_BASE}/api/ocr`, {
          method: 'POST',
          body: formData,
        })
        const data = await response.json()

        if (!response.ok) {
          this.errorMsg = data.detail || '识别失败，请检查后端服务是否已启动'
          return
        }

        if (data.success) {
          this.blocks = data.blocks
          this.editableText = data.text
          this.$nextTick(this.onImageLoad)
        } else {
          this.errorMsg = data.error || '识别失败'
        }
      } catch (error) {
        this.errorMsg = '无法连接后端服务，请确认已运行 uvicorn main:app --reload'
      } finally {
        this.isProcessing = false
      }
    },
  },
}
</script>

<style>
:root {
  --paper: #efe8d8;
  --paper-light: #f8f3e6;
  --ink: #2b2620;
  --ink-soft: #6b6252;
  --seal: #a33a2e;
  --seal-dark: #7f2c22;
  --seal-tint: #f4dcd8;
  --line: #d8cfb8;
  --line-strong: #c4b99c;

  --font-display: 'Songti SC', 'STSong', 'SimSun', serif;
  --font-body: 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif;
  --font-mono: 'SFMono-Regular', Consolas, monospace;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-body);
}

#app {
  max-width: 1180px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

/* ---------- 头部 ---------- */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line-strong);
  margin-bottom: 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 16px;
}

.seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: var(--seal);
  color: var(--paper-light);
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 22px;
  border-radius: 3px;
  letter-spacing: 0;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.15);
}

.brand-text h1 {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  letter-spacing: 1px;
}

.subtitle {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--ink-soft);
}

.stage-tag {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-soft);
  border: 1px solid var(--line-strong);
  padding: 4px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

/* ---------- 工具栏 ---------- */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}

.btn {
  font-family: var(--font-body);
  font-size: 14px;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: transform 0.15s ease, background 0.15s ease;
}

.btn:active {
  transform: translateY(1px);
}

.btn-ghost {
  background: var(--paper-light);
  border-color: var(--line-strong);
  color: var(--ink);
}

.btn-ghost:hover {
  border-color: var(--seal);
  color: var(--seal);
}

.btn-primary {
  background: var(--seal);
  color: var(--paper-light);
  border-color: var(--seal);
}

.btn-primary:hover:not(:disabled) {
  background: var(--seal-dark);
}

.btn-primary:disabled {
  background: var(--line-strong);
  border-color: var(--line-strong);
  color: var(--paper-light);
  cursor: not-allowed;
}

.file-name {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-soft);
}

.error-msg {
  font-size: 13px;
  color: var(--seal);
}

/* ---------- 工作区：左图右文 ---------- */
.workspace {
  display: grid;
  grid-template-columns: 1fr 1px 1fr;
  gap: 24px;
  align-items: start;
}

.spine {
  align-self: stretch;
  background: repeating-linear-gradient(
    to bottom,
    var(--line-strong) 0,
    var(--line-strong) 6px,
    transparent 6px,
    transparent 12px
  );
}

.panel {
  background: var(--paper-light);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 18px;
}

.panel-label {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--line-strong);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-label.secondary {
  margin-top: 20px;
}

.hint {
  font-family: var(--font-body);
  font-weight: 400;
  font-size: 12px;
  color: var(--ink-soft);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-low {
  background: var(--seal);
}

/* 图片与定位框 */
.image-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
}

.source-image {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 4px;
}

.overlay-box {
  position: absolute;
  border: 1.5px solid transparent;
  background: rgba(163, 58, 46, 0);
  pointer-events: auto;
  transition: background 0.12s ease, border-color 0.12s ease;
}

.overlay-box.active {
  border-color: var(--seal);
  background: rgba(163, 58, 46, 0.15);
}

.overlay-box.low {
  border-color: rgba(163, 58, 46, 0.35);
}

.overlay-box.low.active {
  border-color: var(--seal);
  background: rgba(163, 58, 46, 0.22);
}

/* 文字块 */
.text-blocks {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  line-height: 1.9;
}

.text-chip {
  font-family: var(--font-display);
  font-size: 15px;
  padding: 2px 4px;
  border-radius: 3px;
  cursor: default;
  border: 1px solid transparent;
}

.text-chip.low {
  color: var(--seal-dark);
  background: var(--seal-tint);
}

.text-chip.active {
  border-color: var(--seal);
  background: var(--seal-tint);
}

.placeholder {
  color: var(--ink-soft);
  font-size: 13px;
}

.edit-area {
  width: 100%;
  margin-top: 10px;
  font-family: var(--font-display);
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  padding: 12px;
  resize: vertical;
}

.edit-area:focus-visible {
  outline: 2px solid var(--seal);
  outline-offset: 1px;
}

/* ---------- 空状态 ---------- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 80px 20px;
  color: var(--ink-soft);
  border: 1px dashed var(--line-strong);
  border-radius: 6px;
  background: var(--paper-light);
}

.seal-big {
  width: 64px;
  height: 64px;
  font-size: 32px;
  opacity: 0.6;
}

/* ---------- 响应式 ---------- */
@media (max-width: 860px) {
  .workspace {
    grid-template-columns: 1fr;
  }
  .spine {
    display: none;
  }
  .topbar {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>
