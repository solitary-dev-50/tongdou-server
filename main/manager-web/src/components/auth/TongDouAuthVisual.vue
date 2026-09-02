<template>
  <section
    class="tongdou-auth-visual"
    aria-label="TongDou"
    @mousemove="handlePointerMove"
    @mouseleave="resetEyeOffset"
  >
    <div class="tongdou-auth-visual__stage">
      <div class="tongdou-auth-visual__image-wrap">
        <img
          class="tongdou-auth-visual__image"
          src="@/assets/login/tongdou-auth.png"
          alt="TongDou"
        />

        <svg
          class="tongdou-auth-visual__oled"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          role="img"
          aria-label="TongDou OLED eyes"
        >
          <g :transform="eyeTransform">
            <rect
              class="tongdou-auth-visual__eye"
              x="25"
              :y="eyeY"
              width="13"
              :height="eyeHeight"
              rx="2.2"
              :opacity="eyeOpacity"
            />
            <rect
              class="tongdou-auth-visual__eye"
              x="62"
              :y="eyeY"
              width="13"
              :height="eyeHeight"
              rx="2.2"
              :opacity="eyeOpacity"
            />
          </g>
        </svg>
      </div>
    </div>

    <div class="tongdou-auth-visual__dialogue" aria-live="polite">
      <span class="tongdou-auth-visual__prompt">TD://</span>
      <span>{{ displayedDialogue }}</span>
      <span v-if="isTyping && !reducedMotion" class="tongdou-auth-visual__cursor" aria-hidden="true"></span>
    </div>
  </section>
</template>

<script>
const SUPPORTED_STATES = ["boot", "idle", "look", "privacy", "submitting", "suspicious", "success"];

export default {
  name: "TongDouAuthVisual",
  props: {
    state: {
      type: String,
      default: "boot",
      validator: (value) => SUPPORTED_STATES.includes(value),
    },
    mode: {
      type: String,
      default: "login",
      validator: (value) => ["login", "register"].includes(value),
    },
    locale: {
      type: String,
      default: "zh_CN",
    },
  },
  data() {
    return {
      internalState: "boot",
      displayedDialogue: "",
      activeDialogueKey: "boot",
      isTyping: false,
      blinkActive: false,
      eyeOffsetX: 0,
      eyeOffsetY: 0,
      reducedMotion: false,
      motionQuery: null,
      bootTimer: null,
      stateTimer: null,
      blinkTimer: null,
      blinkCloseTimer: null,
      secondBlinkTimer: null,
      typeTimer: null,
    };
  },
  computed: {
    isChinese() {
      return String(this.locale || "").startsWith("zh");
    },
    eyeTransform() {
      return `translate(${this.eyeOffsetX} ${this.eyeOffsetY})`;
    },
    eyeOpacity() {
      return this.internalState === "boot" ? 0 : 1;
    },
    eyeHeight() {
      if (this.internalState === "privacy" || this.internalState === "submitting" || this.blinkActive) {
        return 2.2;
      }
      if (this.internalState === "suspicious") {
        return 9;
      }
      return 27;
    },
    eyeY() {
      if (this.internalState === "privacy" || this.internalState === "submitting" || this.blinkActive) {
        return 49;
      }
      if (this.internalState === "suspicious") {
        return 43;
      }
      return 36;
    },
  },
  watch: {
    state: {
      immediate: true,
      handler(nextState) {
        this.applyState(nextState);
      },
    },
    locale() {
      this.showDialogue(this.activeDialogueKey, true);
    },
  },
  mounted() {
    this.motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    this.reducedMotion = this.motionQuery.matches;
    if (this.motionQuery.addEventListener) {
      this.motionQuery.addEventListener("change", this.handleMotionPreferenceChange);
    } else {
      this.motionQuery.addListener(this.handleMotionPreferenceChange);
    }
    this.startBootSequence();
  },
  beforeDestroy() {
    this.clearTimers();
    if (this.motionQuery) {
      if (this.motionQuery.removeEventListener) {
        this.motionQuery.removeEventListener("change", this.handleMotionPreferenceChange);
      } else {
        this.motionQuery.removeListener(this.handleMotionPreferenceChange);
      }
    }
  },
  methods: {
    handleMotionPreferenceChange(event) {
      this.reducedMotion = event.matches;
      this.resetEyeOffset();
      if (this.reducedMotion) {
        this.stopBlinking();
        this.finishTypingImmediately();
      } else if (this.internalState === "idle") {
        this.scheduleBlink();
      }
    },
    startBootSequence() {
      clearTimeout(this.bootTimer);
      clearTimeout(this.stateTimer);
      this.internalState = this.reducedMotion ? "idle" : "boot";
      if (this.reducedMotion) {
        this.showDialogue("boot", true);
        return;
      }

      this.bootTimer = setTimeout(() => {
        if (this.state !== "boot" && this.state !== "idle") {
          return;
        }
        this.internalState = "idle";
        this.stateTimer = setTimeout(() => {
          if (this.state !== "boot" && this.state !== "idle") {
            return;
          }
          this.blinkActive = true;
          this.blinkCloseTimer = setTimeout(() => {
            this.blinkActive = false;
            this.showDialogue("boot");
            this.scheduleBlink();
          }, 160);
        }, 190);
      }, 340);
    },
    applyState(nextState) {
      clearTimeout(this.stateTimer);
      this.resetEyeOffset();

      if (nextState === "boot") {
        if (this._isMounted) {
          this.startBootSequence();
        }
        return;
      }

      if (nextState === "privacy") {
        this.internalState = "look";
        const delay = this.reducedMotion ? 0 : 200;
        this.stateTimer = setTimeout(() => {
          if (this.state === "privacy") {
            this.internalState = "privacy";
            this.showDialogue("privacy");
          }
        }, delay);
        return;
      }

      if (nextState === "submitting") {
        this.internalState = "submitting";
        return;
      }

      this.internalState = nextState;
      if (nextState === "success") {
        this.showDialogue("success");
      } else if (nextState === "suspicious") {
        this.showDialogue("suspicious");
      }

      if (nextState === "idle") {
        this.scheduleBlink();
      } else {
        this.stopBlinking();
      }
    },
    getDialogue(key) {
      const chinese = {
        register: "准备创建账号？胆子不小。",
        privacy: "放心，人类。我也是有原则的。",
        success: "哼。准你进去。",
        suspicious: "就这？还特意让我闭眼？",
      };
      const english = {
        register: "Creating an account? Brave.",
        privacy: "Relax, human. I have standards.",
        success: "Hmph. You may enter.",
        suspicious: "You closed my eyes for THAT?",
      };

      if (key === "boot") {
        if (this.mode === "register") {
          return this.isChinese ? chinese.register : english.register;
        }
        const bootLines = this.isChinese
          ? [
              "嗨，人类。你欠我的咖啡什么时候结清？",
              "又是你？我刚才正享受清静呢。",
              "登录吧。反正我已经在鄙视你了。",
              "服务器没事。我比较担心你。",
            ]
          : [
              "Hey, human. When are you paying off your coffee debt?",
              "You again? I was enjoying the silence.",
              "Go ahead. Log in. I'm judging you anyway.",
              "Server's fine. I'm more worried about you.",
            ];
        return bootLines[Math.floor(Math.random() * bootLines.length)];
      }

      return (this.isChinese ? chinese : english)[key] || "";
    },
    showDialogue(key, immediate = false) {
      this.activeDialogueKey = key;
      const text = this.getDialogue(key);
      clearTimeout(this.typeTimer);

      if (this.reducedMotion || immediate) {
        this.displayedDialogue = text;
        this.isTyping = false;
        return;
      }

      this.displayedDialogue = "";
      this.isTyping = true;
      let index = 0;
      const typeNextCharacter = () => {
        if (index >= text.length) {
          this.isTyping = false;
          return;
        }
        const character = text[index];
        this.displayedDialogue += character;
        index += 1;
        const punctuationPause = /[，。！？,.!?]/.test(character) ? 90 : 0;
        const speed = 25 + Math.floor(Math.random() * 21);
        this.typeTimer = setTimeout(typeNextCharacter, speed + punctuationPause);
      };
      typeNextCharacter();
    },
    finishTypingImmediately() {
      clearTimeout(this.typeTimer);
      this.displayedDialogue = this.getDialogue(this.activeDialogueKey);
      this.isTyping = false;
    },
    scheduleBlink(initialDelay = null) {
      if (this.reducedMotion || this.internalState !== "idle") {
        return;
      }
      clearTimeout(this.blinkTimer);
      const delay = initialDelay === null ? 4000 + Math.floor(Math.random() * 4001) : initialDelay;
      this.blinkTimer = setTimeout(this.performBlink, delay);
    },
    performBlink() {
      if (this.reducedMotion || this.internalState !== "idle") {
        return;
      }
      this.blinkActive = true;
      const closeDuration = 120 + Math.floor(Math.random() * 101);
      this.blinkCloseTimer = setTimeout(() => {
        this.blinkActive = false;
        if (Math.random() < 0.12) {
          this.secondBlinkTimer = setTimeout(() => {
            this.blinkActive = true;
            this.blinkCloseTimer = setTimeout(() => {
              this.blinkActive = false;
              this.scheduleBlink();
            }, closeDuration);
          }, 130);
        } else {
          this.scheduleBlink();
        }
      }, closeDuration);
    },
    stopBlinking() {
      clearTimeout(this.blinkTimer);
      clearTimeout(this.blinkCloseTimer);
      clearTimeout(this.secondBlinkTimer);
      this.blinkActive = false;
    },
    handlePointerMove(event) {
      if (
        this.reducedMotion ||
        window.innerWidth <= 800 ||
        ["privacy", "submitting", "suspicious"].includes(this.internalState)
      ) {
        return;
      }
      const bounds = event.currentTarget.getBoundingClientRect();
      const normalizedX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
      const normalizedY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
      this.eyeOffsetX = Math.max(-2.4, Math.min(2.4, normalizedX * 2.4));
      this.eyeOffsetY = Math.max(-1.4, Math.min(1.4, normalizedY * 1.4));
    },
    resetEyeOffset() {
      this.eyeOffsetX = 0;
      this.eyeOffsetY = 0;
    },
    clearTimers() {
      clearTimeout(this.bootTimer);
      clearTimeout(this.stateTimer);
      clearTimeout(this.blinkTimer);
      clearTimeout(this.blinkCloseTimer);
      clearTimeout(this.secondBlinkTimer);
      clearTimeout(this.typeTimer);
    },
  },
};
</script>

<style lang="scss" scoped>
.tongdou-auth-visual {
  position: relative;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #d7f8ff;
  isolation: isolate;
}

.tongdou-auth-visual::before {
  position: absolute;
  z-index: -4;
  inset: -12% -10% -10% -16%;
  background:
    radial-gradient(
      ellipse 72% 18% at 43% 70%,
      rgba(90, 105, 112, 0.035) 0%,
      rgba(11, 18, 23, 0) 74%
    ),
    radial-gradient(
      ellipse at 43% 47%,
      rgba(83, 107, 118, 0.045) 0%,
      rgba(54, 76, 87, 0.03) 48%,
      rgba(11, 18, 23, 0) 82%
    );
  content: "";
  pointer-events: none;
}

.tongdou-auth-visual__stage {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  isolation: isolate;
}

.tongdou-auth-visual__stage::before {
  position: absolute;
  z-index: -2;
  top: 53%;
  left: 43%;
  width: 118%;
  height: 92%;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at center,
    rgba(68, 98, 112, 0.1) 0%,
    rgba(43, 70, 83, 0.06) 44%,
    rgba(11, 18, 23, 0) 76%
  );
  content: "";
  pointer-events: none;
  transform: translate(-50%, -50%);
}

.tongdou-auth-visual__image-wrap {
  position: relative;
  z-index: 0;
  width: min(82%, 620px);
  aspect-ratio: 3368 / 3000;
  isolation: isolate;
  transform: translate(-5%, 34px);
}

.tongdou-auth-visual__image-wrap::before {
  position: absolute;
  z-index: -1;
  right: 24%;
  bottom: 4.5%;
  left: 23%;
  height: 5%;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at center,
    rgba(0, 0, 0, 0.46) 0%,
    rgba(0, 0, 0, 0.27) 46%,
    rgba(0, 0, 0, 0) 78%
  );
  content: "";
  filter: blur(4px);
  pointer-events: none;
}

.tongdou-auth-visual__image-wrap::after {
  position: absolute;
  z-index: -2;
  right: 5%;
  bottom: -0.5%;
  left: 4%;
  height: 13%;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at center,
    rgba(0, 0, 0, 0.16) 0%,
    rgba(0, 0, 0, 0.08) 54%,
    rgba(0, 0, 0, 0) 80%
  );
  content: "";
  filter: blur(12px);
  pointer-events: none;
}

.tongdou-auth-visual__image {
  position: absolute;
  z-index: 1;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter: brightness(0.95) saturate(0.96) contrast(1.04);
}

.tongdou-auth-visual__oled {
  /* 正式 PNG 的 OLED 透视定位参数统一在这里调整。 */
  --oled-top: 28.3%;
  --oled-left: 46.6%;
  --oled-width: 24.5%;
  --oled-height: 21.3%;
  --oled-rotate: -7.5deg;
  --oled-skew: 20deg;

  position: absolute;
  z-index: 2;
  top: var(--oled-top);
  left: var(--oled-left);
  width: var(--oled-width);
  height: var(--oled-height);
  overflow: visible;
  filter: drop-shadow(0 1px 3px rgba(105, 231, 245, 0.08));
  pointer-events: none;
  transform-origin: 0 0;
  transform: rotate(var(--oled-rotate)) skewX(var(--oled-skew));
}

.tongdou-auth-visual__eye {
  fill: #69e7f5;
  filter: drop-shadow(0 0 1px rgba(105, 231, 245, 0.18));
  transition: y 90ms ease, height 90ms ease, opacity 180ms ease;
}

.tongdou-auth-visual__dialogue {
  width: min(80%, 560px);
  min-height: 46px;
  margin-top: 36px;
  padding: 13px 0 0 18px;
  border-left: 2px solid rgba(105, 231, 245, 0.58);
  color: #c8d7dd;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 14px;
  line-height: 1.65;
  text-align: left;
  letter-spacing: 0.01em;
  transform: translateX(2%);
}

.tongdou-auth-visual__prompt {
  margin-right: 9px;
  color: #69e7f5;
  font-size: 11px;
  letter-spacing: 0.12em;
}

.tongdou-auth-visual__cursor {
  display: inline-block;
  width: 7px;
  height: 14px;
  margin-left: 4px;
  vertical-align: -2px;
  background: #69e7f5;
  animation: tongdou-cursor 0.8s steps(1) infinite;
}

@keyframes tongdou-cursor {
  50% {
    opacity: 0;
  }
}

@media (max-width: 800px) {
  .tongdou-auth-visual__image-wrap {
    width: min(82%, 320px);
    transform: translate(-3%, 18px);
  }

  .tongdou-auth-visual__dialogue {
    width: min(88%, 390px);
    min-height: 42px;
    margin-top: 22px;
    font-size: 12px;
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tongdou-auth-visual__eye,
  .tongdou-auth-visual__cursor {
    transition: none;
    animation: none;
  }
}
</style>
