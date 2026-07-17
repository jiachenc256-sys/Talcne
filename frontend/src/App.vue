<template>
  <div id="app">
    <header class="topbar">
      <div class="brand">
        <span class="seal">弾</span>
        <div class="brand-text">
          <h1>弹词文字识别助手</h1>
          <p class="subtitle">上传刻本图片（可多张）或PDF · 自动识别 · 逐字校对</p>
        </div>
      </div>
      <div class="topbar-right">
        <span class="stage-tag">MVP · 第一阶段</span>
        <nav class="top-nav">
          <button
            class="nav-link"
            :class="{ active: currentView === 'main' }"
            @click="currentView = 'main'"
          >
            识别工具
          </button>
          <button
            class="nav-link"
            :class="{ active: currentView === 'resources' }"
            @click="currentView = 'resources'"
          >
            资源
          </button>
          <button
            class="nav-link"
            :class="{ active: currentView === 'about' }"
            @click="currentView = 'about'"
          >
            关于
          </button>
        </nav>
      </div>
    </header>

    <div v-if="draftBanner.visible" class="draft-banner">
      <span class="draft-banner-text">
        📝 检测到 {{ draftBanner.savedAt }} 保存的未完成校对草稿
        <template v-if="draftBanner.fileNames.length">（来自：{{ draftBanner.fileNames.join('、') }}）</template>
      </span>
      <div class="draft-banner-actions">
        <button class="btn btn-ghost btn-small" @click="restoreDraft">恢复到编辑框</button>
        <button class="chip-remove" title="清除草稿" @click="dismissDraft">×</button>
      </div>
    </div>

    <template v-if="currentView === 'main'">
    <section class="toolbar">
      <label class="btn btn-ghost">
        选择图片 / PDF
        <input
          type="file"
          accept="image/*,application/pdf"
          multiple
          hidden
          @change="handleInitialSelect"
        />
      </label>
      <label v-if="selectedFiles.length && !isPdfMode" class="btn btn-ghost">
        追加图片
        <input type="file" accept="image/*" multiple hidden @change="handleAppendImages" />
      </label>
      <button
        class="btn btn-primary"
        :disabled="!selectedFiles.length || isProcessing"
        @click="recognizeText"
      >
        {{ isProcessing ? processingLabel : '开始识别文字' }}
      </button>
      <span v-if="errorMsg" class="error-msg">{{ errorMsg }}</span>
    </section>

    <div v-if="selectedFiles.length && !pages.length" class="file-chips">
      <span v-for="(f, idx) in selectedFiles" :key="'file-' + idx" class="file-chip">
        {{ f.name }}
        <button class="chip-remove" title="移除这个文件" @click="removeFile(idx)">×</button>
      </span>
    </div>

    <section v-if="selectedFiles.length || editableText.trim()" class="workspace-wrap">
      <div v-if="pages.length > 1" class="page-tabs">
        <button
          v-for="(p, idx) in pages"
          :key="'page-' + idx"
          class="page-tab"
          :class="{ active: idx === currentPageIndex }"
          @click="switchPage(idx)"
        >
          第{{ p.page }}页
        </button>
      </div>

      <div class="workspace">
        <div class="panel image-panel">
          <p class="panel-label">
            刻本原图
            <span v-if="pages.length" class="hint">共 {{ pages.length }} 页</span>
          </p>
          <div class="image-wrapper" ref="wrapperRef">
            <img
              v-if="previewSrc"
              ref="imgRef"
              class="source-image"
              :src="previewSrc"
              alt="弹词刻本原图"
              @load="onImageLoad"
            />
            <div v-else class="pdf-placeholder">
              <template v-if="isPdfMode">
                📄 已选择 PDF：{{ selectedFiles[0] && selectedFiles[0].name }}
                <br />
                点击上方「开始识别文字」后，这里会显示每一页的预览
              </template>
              <template v-else-if="selectedFiles.length">
                🖼️ 已选择 {{ selectedFiles.length }} 张图片
                <br />
                点击上方「开始识别文字」后，这里会依次显示每一张的预览
              </template>
              <template v-else>
                📝 当前显示的是恢复的校对草稿文字，没有对应的原图预览
                <br />
                如需核对原图，请重新上传文件
              </template>
            </div>
            <div
              v-for="(block, idx) in currentBlocks"
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

          <div v-if="pages.length" class="result-actions">
            <button class="btn btn-ghost btn-small" @click="toggleSimplified">
              {{ isSimplified ? '转换为繁体' : '转换为简体' }}
            </button>
          </div>

          <div v-if="pages.length" class="text-blocks">
            <span
              v-for="(block, idx) in currentBlocks"
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

          <p class="panel-label secondary">
            可编辑全文
            <span v-if="pages.length > 1" class="hint">已包含全部 {{ pages.length }} 页，按页码分隔</span>
          </p>
          <textarea
            class="edit-area"
            v-model="editableText"
            placeholder="识别结果将出现在这里，你可以直接修改校对…"
            rows="10"
          ></textarea>
          <div v-if="pages.length" class="export-controls">
            <button
              class="btn btn-ghost btn-small"
              :disabled="!editableText.trim()"
              @click="exportTxt(editableText, '弹词识别结果')"
            >
              导出为 TXT
            </button>
            <button
              class="btn btn-ghost btn-small"
              :disabled="!editableText.trim()"
              @click="exportDocx(editableText, '弹词识别结果')"
            >
              导出为 Word
            </button>
          </div>

          <p class="panel-label secondary">翻译</p>
          <div class="translate-controls">
            <select v-model="targetLang" class="lang-select">
              <option v-for="(label, code) in languageOptions" :key="code" :value="code">
                {{ label }}
              </option>
            </select>
            <button
              class="btn btn-ghost btn-small"
              :disabled="!editableText.trim() || isTranslating"
              @click="translateText"
            >
              {{ isTranslating ? '翻译中…' : `翻译成${languageOptions[targetLang]}` }}
            </button>
          </div>
          <p v-if="translateError" class="error-msg">{{ translateError }}</p>
          <textarea
            v-if="translatedText"
            class="edit-area"
            :value="translatedText"
            readonly
            rows="8"
          ></textarea>
          <div v-if="translatedText" class="export-controls">
            <button class="btn btn-ghost btn-small" @click="exportTxt(translatedText, '弹词翻译结果')">
              导出译文为 TXT
            </button>
          </div>
        </div>
      </div>
    </section>

    <section v-else class="empty-state">
      <span class="seal seal-big">弾</span>
      <p>请选择一张或多张弹词刻本图片，或者一份PDF开始</p>
    </section>
    </template>

    <template v-else-if="currentView === 'resources'">
      <section class="resources-page">
        <div class="about-section">
          <h2>弹词经典作品</h2>
          <p>
            这里整理了弹词这个门类里比较有代表性、常被提到的几部经典作品，供你研究刻本时作为背景参考。
          </p>
        </div>

        <article v-for="work in classicWorks" :key="work.title" class="work-card">
          <h3>{{ work.title }}</h3>
          <p class="work-meta">{{ work.meta }}</p>

          <div class="work-section">
            <h4>内容梗概</h4>
            <p>{{ work.summary }}</p>
          </div>
          <div class="work-section">
            <h4>现存版本</h4>
            <p>{{ work.versions }}</p>
          </div>
          <div class="work-section">
            <h4>影响与地位</h4>
            <p>{{ work.influence }}</p>
          </div>
          <div class="work-section">
            <h4>与其他作品的关系</h4>
            <p>{{ work.relations }}</p>
          </div>

          <button class="btn btn-ghost btn-small work-read-btn" @click="openReader(work)">
            阅读全文 →
          </button>
        </article>
      </section>
    </template>

    <template v-else-if="currentView === 'reader'">
      <section class="reader-page">
        <button class="btn btn-ghost btn-small reader-back" @click="currentView = 'resources'">
          ← 返回资源
        </button>

        <h2 class="reader-title">{{ readerTitle }}</h2>

        <div v-if="readerLoading" class="reader-status">加载中…</div>

        <div v-else-if="readerError" class="reader-status">
          📖 这部作品还没有收录全文，欢迎期待更新。
        </div>

        <div v-else-if="readerData" class="reader-body">
          <div class="reader-chapter-nav">
            <button
              class="btn btn-ghost btn-small"
              :disabled="readerChapterIndex === 0"
              @click="readerChapterIndex--"
            >
              ← 上一章
            </button>
            <select v-model.number="readerChapterIndex" class="lang-select reader-chapter-select">
              <option v-for="(chapter, idx) in readerData.chapters" :key="idx" :value="idx">
                {{ chapter.title }}
              </option>
            </select>
            <button
              class="btn btn-ghost btn-small"
              :disabled="readerChapterIndex >= readerData.chapters.length - 1"
              @click="readerChapterIndex++"
            >
              下一章 →
            </button>
          </div>

          <article class="reader-text">
            <h3>{{ currentReaderChapter && currentReaderChapter.title }}</h3>
            <p
              v-for="(para, idx) in currentReaderParagraphs"
              :key="idx"
              class="reader-paragraph"
            >
              {{ para }}
            </p>
          </article>
        </div>
      </section>
    </template>

    <template v-else-if="currentView === 'about'">
      <section class="about-page">
        <div class="about-section">
          <h2>关于这个项目</h2>
          <p>
            「弹词文字识别助手」是一个用来辅助识别、校对弹词刻本文字的小工具，目标是让整理古籍刻本文字
            这件事更省力一点——上传一张刻本图片或PDF，自动识别出文字，再逐字跟原图对照校对，减少纯手工
            抄录的工作量。目前还是第一阶段的MVP（最小可行产品），功能和识别准确率都还在持续完善中。
          </p>
        </div>

        <div class="about-section">
          <h2>开发者</h2>
          <p>本项目由 <strong>Jiachen Chen (Alice)</strong> 独立开发和维护。</p>
        </div>

        <!--
          第三方服务/开源库板块按你的要求隐藏了。
          提醒一下（不是要改你的决定，就留个记录）：这里用到的PyMuPDF是AGPL协议，
          该协议要求"网络使用也要能获取到源代码"。你的GitHub仓库本身是public的，
          所以源码依然是可以找到的，只是网站上不再主动放入口了。
          以后如果想恢复，把下面这段取消注释就行：

        <div class="about-section">
          <h2>用到的第三方服务和开源库</h2>
          <ul class="about-list">
            <li>文字识别：百度智能云「通用文字识别（高精度版）」</li>
            <li>翻译：百度翻译开放平台「通用文本翻译API」</li>
            <li>PDF转图片：PyMuPDF（<a href="https://pymupdf.readthedocs.io/" target="_blank" rel="noopener">AGPL开源协议</a>）</li>
            <li>繁简转换：opencc-js（开源库）</li>
          </ul>
          <p class="about-note">
            以上服务/库各自遵循其自身的条款和开源协议，与本项目本身的版权分开。其中PDF处理用到的PyMuPDF
            采用AGPL协议，该协议要求：只要用户是通过网络在使用这个功能（比如访问这个网站），就需要能够
            获取到完整的源代码，因此这里附上本项目的
            <a href="https://github.com/jiachenc256-sys/Talcne" target="_blank" rel="noopener">GitHub源码仓库</a>。
          </p>
        </div>
        -->

        <div class="about-section">
          <h2>隐私说明</h2>
          <p>
            上传的图片或PDF会被发送到百度的服务器，用于文字识别和翻译处理；本项目自身的服务器不会保存
            你上传的文件，识别结果也只保留在你当前浏览器的这次会话里，刷新页面就会清空。
          </p>
        </div>

        <div class="about-section">
          <h2>版权</h2>
          <p class="about-note">
            © 2026 弹词文字识别助手。本项目代码保留所有权利（All rights reserved），
            未经许可不得复制、修改或用于其他用途；项目中使用的第三方服务和开源库各自遵循其自身条款。
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<script>
import * as OpenCC from 'opencc-js'
import { Document, Packer, Paragraph, TextRun } from 'docx'

// 后端接口地址：本地开发默认指向 FastAPI 的 8000 端口
// 部署到 Vercel 后，可在项目的环境变量里设置 VITE_API_BASE 指向线上后端地址（如 Render 域名）
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// 接口保护用的共享密钥，要跟后端 APP_SHARED_SECRET 填一样的值。
// 本地开发不设置也能跑（后端没配密钥时不校验）；部署上线建议在 Vercel 里配置。
const APP_SECRET = import.meta.env.VITE_APP_SECRET || ''

// 繁简转换器：纯前端转换，不需要调用任何后端接口
const toSimplified = OpenCC.Converter({ from: 't', to: 'cn' })
const toTraditional = OpenCC.Converter({ from: 'cn', to: 't' })

function isPdfFile(file) {
  return file.type === 'application/pdf' || /\.pdf$/i.test(file.name || '')
}

export default {
  name: 'App',
  data() {
    return {
      currentView: 'main', // 'main' | 'about'
      selectedFiles: [], // 用户选中的文件列表：要么是1个PDF，要么是1张及以上图片
      singlePreviewUrl: null, // 只选了1张图片时，识别前可以直接本地预览用这个
      // pages: 识别结果按页存储。PDF模式下每页是PDF的一页；多图模式下每页对应一张上传的图片。
      // 结构: { page, text, blocks, image }
      pages: [],
      currentPageIndex: 0,
      editableText: '',
      isProcessing: false,
      processingLabel: '识别中…',
      errorMsg: '',
      isSimplified: false,
      hoverIndex: null,
      naturalSize: { width: 0, height: 0 },
      displaySize: { width: 0, height: 0 },
      targetLang: 'en',
      languageOptions: {
        en: '英语',
        jp: '日语',
        kor: '韩语',
        fra: '法语',
        spa: '西班牙语',
        de: '德语',
      },
      translatedText: '',
      isTranslating: false,
      translateError: '',
      draftBanner: {
        visible: false,
        savedAt: '',
        fileNames: [],
        text: '',
      },
      autosaveTimer: null,
      classicWorks: [
        {
          slug: 'zaisheng-yuan',
          title: '《再生缘》',
          meta: '清·陈端生 著（约1751—约1796），梁德绳 续',
          summary:
            '写元代尚书之女孟丽君女扮男装、隐姓埋名考中状元、官至宰相的经历，牵出她与皇甫少华之间几经波折的姻缘。陈端生只写到第十七卷便因病搁笔，故事没能按自己的设想收尾，后由梁德绳续写完成，结局趋于传统的团圆式收场，风格和原作有明显落差。',
          versions:
            '全书早年以抄本形式在民间流传了近百年才有刻本问世，现存较早的刻本是道光三十年（1850）三益堂本。之后陆续出现多个刻本和整理本，近代也有点校本行世。',
          influence:
            '学者陈寅恪晚年专门写了一篇长文研究这部作品，认为它是弹词中成就最高的一部，可以和印度、希腊的史诗相提并论；郭沫若读后深受触动，把它和《红楼梦》并称"南缘北梦"。后世据此改编的评弹、木鱼歌、京剧、话剧等版本很多。',
          relations:
            '常与《天雨花》《笔生花》并称"弹词三大"，三部都出自女性作家之手，主题也都围绕女性突破礼教束缚展开；《笔生花》的作者邱心如在自己书里还专门评论过这部书。',
        },
        {
          slug: 'tianyu-hua',
          title: '《天雨花》',
          meta: '旧题 明末清初·陶贞怀 著（作者存疑）',
          summary:
            '借官员左维明和权臣魏忠贤等人的斗争，重现明末东林党与阉党相争的真实历史，牵涉梃击、红丸、移宫这几桩晚明著名疑案。左维明的女儿左仪贞也是书中重要人物，作者借她的经历表达了对女性处境的关注。',
          versions: '成书约在顺治八年（1651），现存有同治年间纬文堂等多种刻本传世，版本相对完整。',
          influence:
            '清代学者杨芳灿把它和《红楼梦》并称"南花北梦"，评价很高。这部书后来被京剧、评剧、越剧、川剧、闽剧等多个地方戏种改编搬演，影响延续到今天的戏曲舞台。',
          relations:
            '和《再生缘》《笔生花》并称"弹词三大"。跟另外两部不同的是，它更侧重政治历史题材，而不是才子佳人式的爱情故事。',
        },
        {
          slug: 'yu-qingting',
          title: '《玉蜻蜓》',
          meta: '苏州弹词（评弹）传统书目，作者及成书年代不可考',
          summary:
            '分前后两段：前段写沈君卿寻访申贵升的经历；后段是主线，写苏州富商申贵升迷恋尼姑志贞、病死庵堂，志贞暗中产下遗腹子并托人送出，孩子几经辗转被徐家收养、改名徐元宰，长大后科举中式，最终在庵堂认回生母、恢复本姓。',
          versions:
            '作为口传的评弹书目，没有固定的"原著文本"，主要以历代艺人的演出脚本形式流传。1950年代评弹名家蒋月泉和作家陈灵犀曾对传统脚本做过系统整理，形成了现在通行的演出版本；此外还有周玉泉等名家留下的录音、录像资料。',
          influence:
            '是苏州评弹最经典的长篇书目之一，"庵堂认母""庵堂想会"等选段至今仍是常演的热门折子；名家周玉泉据此形成了自己的"周调"唱腔流派。',
          relations:
            '和《珍珠塔》《义妖传》一样属于用苏州方言演唱的"土音弹词"（区别于《再生缘》《天雨花》这类用官话写成的"国音弹词"），是苏州评弹的代表书目之一。',
        },
        {
          slug: 'zhenzhu-ta',
          title: '《珍珠塔》',
          meta: '全称《孝义真迹珍珠塔全传》，作者佚名，清乾隆年间已有刻本',
          summary:
            '落魄书生方卿投奔襄阳的姑母求助反被羞辱，表姐陈翠娥同情他，偷偷把传家宝"珍珠塔"送给他作盘缠。方卿后来考中状元，特意扮成道士回乡，用一段讽刺的道情曲羞讽势利的姑母，最终姑侄和解，他与翠娥完婚。',
          versions:
            '现存最早的是乾隆年间由艺人周殊士作序的刻本，后经马如飞等历代艺人不断增补加工，逐渐形成了流传更广的版本。马如飞本的唱词就有三千多档、一万五千余句，是评弹里公认篇幅唱词都很庞大的一部。',
          influence:
            '被认为是评弹传统书目里艺术水准最高的几部之一，唱词讲究、典故密集，文学性很强。"方卿唱道情"是至今传唱的经典选段，也被改编成锡剧、越剧、枣梆、吕剧等多个地方戏版本。',
          relations: '和《玉蜻蜓》《义妖传》同属苏州方言的土音弹词系统，故事背景相传出自苏州同里的真实人物轶事。',
        },
        {
          slug: 'bisheng-hua',
          title: '《笔生花》',
          meta: '清·邱心如 著，咸丰七年（1857）首次刊行',
          summary:
            '同样是女扮男装、考取功名的题材，女主角姜德华女扮男装闯出一片天地。作者邱心如在书里明确表示自己是接着《再生缘》《天雨花》的路子写下去的，但对陈端生笔下女主角的一些出格举动并不完全认同，在序言里直接提出了批评。',
          versions:
            '咸丰七年（1857）首次刊行，同治十一年（1872）又出过修订版，篇幅浩大，有说唱有诗文，是这类长篇弹词里体量很大的一部。',
          influence:
            '常与《再生缘》《天雨花》并列讨论，被视为清代女性弹词创作的重要收官之作。也因为篇幅和技巧上的"雕琢"感，曾被个别学者认为不如另外两部质朴自然。',
          relations:
            '是"弹词三大"里最晚出现的一部，作者与陈端生等前辈作者之间存在明显的对话和呼应关系，某种程度上是一场跨越几十年的女性作家之间的隔空商榷。',
        },
        {
          slug: 'shuangzhu-feng',
          title: '《双珠凤》',
          meta: '才子佳人题材传统曲艺剧目，有扬州弹词、锡剧等多个地方版本',
          summary:
            '洛阳才子文必正邂逅吏部天官之女霍定金，两人以一对珠凤发簪定情。文必正为接近心上人卖身为奴，二人几经家变、蒙冤、逼婚、女扮男装出逃等波折，最终苦尽甘来、重逢完婚。',
          versions:
            '没有单一的"原始文本"，而是在扬州弹词、锡剧、越剧等不同地方曲艺/戏曲系统里各自有自己的演出脚本，情节框架大体一致，细节处理各有取舍。',
          influence: '1963年曾被拍成锡剧电影，是几代地方戏演员的看家戏之一；近年在扬州弹词的舞台上依然常演常新。',
          relations: '跟《珍珠塔》《玉蜻蜓》一样属于才子佳人加家族波折的叙事模式，反映了这类弹词故事在不同方言区之间流传、变形的现象。',
        },
        {
          slug: 'yiyao-zhuan',
          title: '《义妖传》',
          meta: '苏州弹词，由清代艺人陈遇乾整理定型，题《绣像义妖全传》',
          summary:
            '讲的就是白娘子和许仙的白蛇传说：西湖借伞相识、端午现出蛇形惊吓许仙、盗仙草救夫、水漫金山、断桥重逢、被镇压在雷峰塔下，直到儿子高中状元祭塔团圆，是白蛇故事流传过程中定型最完整的一版。',
          versions:
            '在陈遇乾整理的正传之后，还有一段以角色胡媚娘为主角的"后传"，普遍被认为艺术水准不如正传。这部弹词至今没有经过完整的现代学术整理出版，主要还是以旧时的线装本形式零散流传，收藏市场上常见品相不全的散册。',
          influence:
            '上承冯梦龙话本《白娘子永镇雷峰塔》、方成培传奇《雷峰塔》等更早的白蛇故事文本，陈遇乾的这版基本奠定了后世白蛇传说家喻户晓的完整情节框架，京剧、越剧等后来的白蛇传戏曲很大程度上都延续了这里定下的故事结构。',
          relations: '和《玉蜻蜓》《珍珠塔》同属苏州土音弹词系统。',
        },
      ],
      readerTitle: '',
      readerSlug: '',
      readerData: null,
      readerLoading: false,
      readerError: false,
      readerChapterIndex: 0,
    }
  },
  mounted() {
    this.checkForDraft()
  },
  watch: {
    editableText(newVal) {
      clearTimeout(this.autosaveTimer)
      this.autosaveTimer = setTimeout(() => {
        this.saveDraft(newVal)
      }, 800)
    },
  },
  computed: {
    isPdfMode() {
      return this.selectedFiles.length === 1 && isPdfFile(this.selectedFiles[0])
    },
    currentBlocks() {
      const p = this.pages[this.currentPageIndex]
      return p ? p.blocks : []
    },
    previewSrc() {
      const p = this.pages[this.currentPageIndex]
      if (p) return p.image
      return this.singlePreviewUrl
    },
    currentReaderChapter() {
      if (!this.readerData) return null
      return this.readerData.chapters[this.readerChapterIndex] || null
    },
    currentReaderParagraphs() {
      const chapter = this.currentReaderChapter
      if (!chapter || !chapter.text) return []
      return chapter.text.split('\n').filter((line) => line.trim())
    },
  },
  methods: {
    saveDraft(text) {
      try {
        if (!text || !text.trim()) {
          localStorage.removeItem('tanci-ocr-draft')
          return
        }
        const payload = {
          text,
          savedAt: Date.now(),
          fileNames: this.selectedFiles.map((f) => f.name),
        }
        localStorage.setItem('tanci-ocr-draft', JSON.stringify(payload))
      } catch (e) {
        // 浏览器本地存储可能满了或者被禁用（比如无痕模式），静默失败即可，不影响正常使用
        console.warn('自动保存草稿失败：', e)
      }
    },
    checkForDraft() {
      try {
        const raw = localStorage.getItem('tanci-ocr-draft')
        if (!raw) return
        const draft = JSON.parse(raw)
        if (!draft.text || !draft.text.trim()) return
        this.draftBanner = {
          visible: true,
          savedAt: this.formatDraftTime(draft.savedAt),
          fileNames: draft.fileNames || [],
          text: draft.text,
        }
      } catch (e) {
        console.warn('读取草稿失败：', e)
      }
    },
    formatDraftTime(ts) {
      if (!ts) return ''
      const diffMinutes = Math.round((Date.now() - ts) / 60000)
      if (diffMinutes < 1) return '刚刚'
      if (diffMinutes < 60) return `${diffMinutes}分钟前`
      const diffHours = Math.round(diffMinutes / 60)
      if (diffHours < 24) return `${diffHours}小时前`
      const diffDays = Math.round(diffHours / 24)
      return `${diffDays}天前`
    },
    restoreDraft() {
      this.editableText = this.draftBanner.text
      this.draftBanner.visible = false
    },
    dismissDraft() {
      localStorage.removeItem('tanci-ocr-draft')
      this.draftBanner.visible = false
    },
    async openReader(work) {
      this.currentView = 'reader'
      this.readerTitle = work.title
      this.readerSlug = work.slug
      this.readerData = null
      this.readerError = false
      this.readerChapterIndex = 0
      this.readerLoading = true
      try {
        const response = await fetch(`/texts/${work.slug}.json`)
        if (!response.ok) throw new Error('未找到')
        const data = await response.json()
        if (!data.chapters || !data.chapters.length) throw new Error('内容为空')
        this.readerData = data
      } catch (e) {
        this.readerError = true
      } finally {
        this.readerLoading = false
      }
    },
    resetResults() {
      this.pages = []
      this.currentPageIndex = 0
      this.editableText = ''
      this.errorMsg = ''
      this.isSimplified = false
      this.translatedText = ''
      this.translateError = ''
    },
    handleInitialSelect(event) {
      const files = Array.from(event.target.files || [])
      event.target.value = '' // 允许重复选中同一批文件也能触发change
      if (!files.length) return

      this.resetResults()

      if (files.length === 1 && isPdfFile(files[0])) {
        this.selectedFiles = files
        this.singlePreviewUrl = null
        return
      }

      const images = files.filter((f) => !isPdfFile(f))
      if (images.length !== files.length) {
        this.errorMsg = 'PDF请单独上传，不要和图片混选，已自动忽略PDF文件'
      }
      this.selectedFiles = images
      this.singlePreviewUrl = images.length === 1 ? URL.createObjectURL(images[0]) : null
    },
    handleAppendImages(event) {
      const files = Array.from(event.target.files || []).filter((f) => !isPdfFile(f))
      event.target.value = ''
      if (!files.length) return

      this.selectedFiles = [...this.selectedFiles, ...files]
      this.singlePreviewUrl =
        this.selectedFiles.length === 1 ? URL.createObjectURL(this.selectedFiles[0]) : null
      // 有新文件加入，之前的识别结果作废，需要重新点一次「开始识别文字」
      this.resetResults()
    },
    removeFile(idx) {
      this.selectedFiles.splice(idx, 1)
      this.singlePreviewUrl =
        this.selectedFiles.length === 1 ? URL.createObjectURL(this.selectedFiles[0]) : null
      this.resetResults()
    },
    switchPage(idx) {
      this.currentPageIndex = idx
      this.hoverIndex = null
      this.$nextTick(this.onImageLoad)
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
    toggleSimplified() {
      // 用当前显示的文字（可能已经过用户手动校对）做转换，而不是用最初的识别结果，
      // 这样切换繁简不会覆盖掉用户已经改过的地方
      const converter = this.isSimplified ? toTraditional : toSimplified
      this.editableText = converter(this.editableText)
      this.pages = this.pages.map((p) => ({
        ...p,
        text: converter(p.text),
        blocks: p.blocks.map((b) => ({ ...b, text: converter(b.text) })),
      }))
      this.isSimplified = !this.isSimplified
    },
    async callOcrApi(file) {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(`${API_BASE}/api/ocr`, {
        method: 'POST',
        headers: APP_SECRET ? { 'X-App-Token': APP_SECRET } : {},
        body: formData,
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || '识别失败，请检查后端服务是否已启动')
      }
      return data
    },
    async recognizeText() {
      if (!this.selectedFiles.length) return
      this.isProcessing = true
      this.errorMsg = ''
      this.pages = []
      this.currentPageIndex = 0
      this.processingLabel = '识别中…'

      try {
        if (this.isPdfMode) {
          await this.recognizePdf(this.selectedFiles[0])
        } else {
          await this.recognizeImages(this.selectedFiles)
        }
      } finally {
        this.isProcessing = false
      }
    },
    async recognizePdf(file) {
      try {
        const data = await this.callOcrApi(file)
        if (data.success) {
          this.pages = data.pages || []
          this.editableText = data.text
          this.$nextTick(this.onImageLoad)
        } else {
          this.errorMsg = data.error || '识别失败'
        }
      } catch (error) {
        this.errorMsg = error.message || '无法连接后端服务，请确认后端已经启动/上线'
      }
    },
    async recognizeImages(files) {
      const allPages = []
      const textParts = []
      const multi = files.length > 1

      for (let i = 0; i < files.length; i++) {
        this.processingLabel = multi ? `识别中…（${i + 1}/${files.length}）` : '识别中…'
        const file = files[i]
        try {
          const data = await this.callOcrApi(file)
          if (data.success) {
            const page = data.pages[0]
            allPages.push({
              page: i + 1,
              text: page.text,
              blocks: page.blocks,
              image: URL.createObjectURL(file),
            })
            textParts.push(multi ? `—— 第${i + 1}张 ——\n${page.text}` : page.text)
          } else {
            this.errorMsg = `「${file.name}」：${data.error || '未识别到文字'}`
          }
        } catch (error) {
          this.errorMsg = `「${file.name}」识别失败：${error.message}`
        }
      }

      this.pages = allPages
      this.editableText = textParts.join('\n\n')
      this.$nextTick(this.onImageLoad)
    },
    downloadBlob(blob, filename) {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    },
    exportTxt(text, baseName) {
      if (!text || !text.trim()) return
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
      this.downloadBlob(blob, `${baseName}.txt`)
    },
    async exportDocx(text, baseName) {
      if (!text || !text.trim()) return
      const paragraphs = text
        .split('\n')
        .map((line) => new Paragraph({ children: [new TextRun(line)] }))
      const doc = new Document({ sections: [{ children: paragraphs }] })
      const blob = await Packer.toBlob(doc)
      this.downloadBlob(blob, `${baseName}.docx`)
    },
    async translateText() {
      if (!this.editableText.trim()) return
      this.isTranslating = true
      this.translateError = ''
      try {
        const response = await fetch(`${API_BASE}/api/translate`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(APP_SECRET ? { 'X-App-Token': APP_SECRET } : {}),
          },
          body: JSON.stringify({ text: this.editableText, to: this.targetLang }),
        })
        const data = await response.json()
        if (!response.ok) {
          this.translateError = data.detail || '翻译失败'
          return
        }
        this.translatedText = data.translated
      } catch (error) {
        this.translateError = '无法连接后端服务：' + error.message
      } finally {
        this.isTranslating = false
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

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
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

.top-nav {
  display: flex;
  gap: 4px;
}

.nav-link {
  font-family: var(--font-body);
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 4px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink-soft);
  cursor: pointer;
}

.nav-link:hover {
  color: var(--seal);
}

.nav-link.active {
  background: var(--paper-light);
  border-color: var(--line-strong);
  color: var(--seal);
  font-weight: 600;
}

/* ---------- 工具栏 ---------- */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
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

.error-msg {
  font-size: 13px;
  color: var(--seal);
}

/* ---------- 草稿恢复提示条 ---------- */
.draft-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  background: var(--seal-tint);
  border: 1px solid var(--seal);
  border-radius: 6px;
  padding: 10px 16px;
  margin-bottom: 20px;
}

.draft-banner-text {
  font-size: 13px;
  color: var(--seal-dark);
}

.draft-banner-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ---------- 已选文件列表 ---------- */
.file-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.file-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-soft);
  background: var(--paper-light);
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  padding: 4px 6px 4px 12px;
}

.chip-remove {
  border: none;
  background: transparent;
  color: var(--ink-soft);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 50%;
}

.chip-remove:hover {
  background: var(--seal-tint);
  color: var(--seal-dark);
}

/* ---------- 页码切换 ---------- */
.page-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.page-tab {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--line-strong);
  background: var(--paper-light);
  color: var(--ink-soft);
  cursor: pointer;
}

.page-tab:hover {
  border-color: var(--seal);
  color: var(--seal);
}

.page-tab.active {
  background: var(--seal);
  border-color: var(--seal);
  color: var(--paper-light);
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

.result-actions {
  margin-bottom: 12px;
}

.btn-small {
  padding: 6px 14px;
  font-size: 13px;
}

.export-controls {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.translate-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.lang-select {
  font-family: var(--font-body);
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid var(--line-strong);
  background: var(--paper-light);
  color: var(--ink);
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
  min-height: 120px;
}

.source-image {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 4px;
}

.pdf-placeholder {
  padding: 48px 16px;
  text-align: center;
  color: var(--ink-soft);
  font-size: 13px;
  line-height: 1.8;
  border: 1px dashed var(--line-strong);
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
  min-height: 24px;
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

/* ---------- 关于页面 ---------- */
.about-page {
  max-width: 720px;
}

/* ---------- 资源页面 ---------- */
.resources-page {
  max-width: 780px;
}

.work-card {
  background: var(--paper-light);
  border: 1px solid var(--line);
  border-left: 3px solid var(--seal);
  border-radius: 6px;
  padding: 20px 24px;
  margin-bottom: 20px;
}

.work-card h3 {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 4px;
}

.work-meta {
  font-size: 12px;
  color: var(--ink-soft);
  margin: 0 0 14px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--line-strong);
}

.work-section {
  margin-bottom: 12px;
}

.work-section:last-child {
  margin-bottom: 0;
}

.work-section h4 {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 700;
  color: var(--seal-dark);
  margin: 0 0 4px;
}

.work-section p {
  font-size: 14px;
  line-height: 1.85;
  color: var(--ink);
  margin: 0;
}

.about-section {
  margin-bottom: 32px;
}

.about-section h2 {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  margin: 0 0 10px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--line-strong);
}

.about-section p {
  font-size: 14px;
  line-height: 1.9;
  color: var(--ink);
  margin: 0 0 8px;
}

.about-list {
  font-size: 14px;
  line-height: 2;
  color: var(--ink);
  margin: 0 0 8px;
  padding-left: 20px;
}

.about-list a {
  color: var(--seal);
}

.about-note {
  font-size: 12px;
  color: var(--ink-soft);
}

.work-read-btn {
  margin-top: 4px;
}

/* ---------- 阅读器页面 ---------- */
.reader-page {
  max-width: 720px;
}

.reader-back {
  margin-bottom: 16px;
}

.reader-title {
  font-family: var(--font-display);
  font-size: 22px;
  margin: 0 0 20px;
}

.reader-status {
  padding: 60px 20px;
  text-align: center;
  color: var(--ink-soft);
  border: 1px dashed var(--line-strong);
  border-radius: 6px;
  background: var(--paper-light);
}

.reader-chapter-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.reader-chapter-select {
  flex: 1;
  min-width: 160px;
}

.reader-text {
  background: var(--paper-light);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 28px 32px;
}

.reader-text h3 {
  font-family: var(--font-display);
  font-size: 18px;
  margin: 0 0 20px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--line-strong);
}

.reader-paragraph {
  font-family: var(--font-display);
  font-size: 15px;
  line-height: 2.1;
  color: var(--ink);
  margin: 0 0 16px;
  text-indent: 2em;
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
