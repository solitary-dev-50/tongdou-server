<template>
  <div class="tongdou-auth-page">
    <main class="tongdou-auth-shell">
      <tong-dou-auth-visual ref="authVisual" :state="authState" mode="register" :locale="currentLanguage" />

      <section class="tongdou-auth-panel" aria-labelledby="register-title">
        <div class="tongdou-auth-card" :aria-busy="isSubmitting ? 'true' : 'false'">
          <div class="tongdou-auth-brand">
            <span class="tongdou-auth-brand__name">TongDou</span>
            <span class="tongdou-auth-brand__divider" aria-hidden="true"></span>
            <span class="tongdou-auth-brand__product">Control Center</span>

            <el-dropdown trigger="click" class="tongdou-auth-language"
              @visible-change="handleLanguageDropdownVisibleChange">
              <span class="el-dropdown-link">
                {{ currentLanguageText }}
                <i class="el-icon-arrow-down" :class="{ 'is-open': languageDropdownVisible }"></i>
              </span>
              <el-dropdown-menu slot="dropdown">
                <el-dropdown-item @click.native="changeLanguage('zh_CN')">{{ $t("language.zhCN") }}</el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('zh_TW')">{{ $t("language.zhTW") }}</el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('en')">{{ $t("language.en") }}</el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('de')">{{ $t("language.de") }}</el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('vi')">{{ $t("language.vi") }}</el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('pt_BR')">{{ $t("language.ptBR") }}</el-dropdown-item>
              </el-dropdown-menu>
            </el-dropdown>
          </div>

          <header class="tongdou-auth-heading">
            <div class="tongdou-auth-heading__eyebrow">NEW OPERATOR</div>
            <h1 id="register-title">{{ $t("register.title") }}</h1>
            <p>{{ formSubtitle }}</p>
          </header>

          <form class="tongdou-auth-form" @submit.prevent="register">
            <div v-if="!enableMobileRegister" class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-register-username">
                {{ $t("register.usernamePlaceholder") }}
              </label>
              <div class="tongdou-auth-input">
                <i class="el-icon-user tongdou-auth-input__icon" aria-hidden="true"></i>
                <el-input id="tongdou-register-username" v-model="form.username"
                  :placeholder="$t('register.usernamePlaceholder')" autocomplete="username"
                  @focus="handleIdentityFocus" @blur="handleIdentityBlur" />
              </div>
            </div>

            <template v-if="enableMobileRegister">
              <div class="tongdou-auth-field">
                <label class="tongdou-auth-field__label" for="tongdou-register-mobile">
                  {{ $t("register.mobilePlaceholder") }}
                </label>
                <div class="tongdou-auth-phone">
                  <div class="tongdou-auth-input">
                    <el-select v-model="form.areaCode" aria-label="Area code">
                      <el-option v-for="item in mobileAreaList" :key="item.key"
                        :label="`${item.name} (${item.key})`" :value="item.key" />
                    </el-select>
                  </div>
                  <div class="tongdou-auth-input">
                    <i class="el-icon-mobile-phone tongdou-auth-input__icon" aria-hidden="true"></i>
                    <el-input id="tongdou-register-mobile" v-model="form.mobile"
                      :placeholder="$t('register.mobilePlaceholder')" autocomplete="tel" inputmode="tel"
                      @focus="handleIdentityFocus" @blur="handleIdentityBlur" />
                  </div>
                </div>
              </div>

              <div class="tongdou-auth-field">
                <label class="tongdou-auth-field__label" for="tongdou-register-mobile-captcha">
                  {{ $t("register.captchaPlaceholder") }}
                </label>
                <div class="tongdou-auth-inline">
                  <div class="tongdou-auth-input">
                    <i class="el-icon-key tongdou-auth-input__icon" aria-hidden="true"></i>
                    <el-input id="tongdou-register-mobile-captcha" v-model="form.captcha"
                      :placeholder="$t('register.captchaPlaceholder')" autocomplete="off" />
                  </div>
                  <img v-if="captchaUrl" class="tongdou-auth-captcha" :src="captchaUrl" alt="验证码"
                    @click="fetchCaptcha" />
                </div>
              </div>

              <div class="tongdou-auth-field">
                <label class="tongdou-auth-field__label" for="tongdou-register-sms">
                  {{ $t("register.mobileCaptchaPlaceholder") }}
                </label>
                <div class="tongdou-auth-inline">
                  <div class="tongdou-auth-input">
                    <i class="el-icon-message tongdou-auth-input__icon" aria-hidden="true"></i>
                    <el-input id="tongdou-register-sms" v-model="form.mobileCaptcha"
                      :placeholder="$t('register.mobileCaptchaPlaceholder')" autocomplete="one-time-code"
                      inputmode="numeric" maxlength="6" />
                  </div>
                  <button type="button" class="tongdou-auth-secondary-button"
                    :disabled="!canSendMobileCaptcha" @click="sendMobileCaptcha">
                    {{ countdown > 0 ? `${countdown}${$t("register.secondsLater")}` : $t("register.sendCaptcha") }}
                  </button>
                </div>
              </div>
            </template>

            <div class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-register-password">
                {{ $t("register.passwordPlaceholder") }}
              </label>
              <div class="tongdou-auth-input">
                <i class="el-icon-lock tongdou-auth-input__icon" aria-hidden="true"></i>
                <el-input id="tongdou-register-password" v-model="form.password"
                  :placeholder="$t('register.passwordPlaceholder')" type="password"
                  autocomplete="new-password" show-password
                  @focus="handlePasswordFocus" @blur="handlePasswordBlur" />
              </div>
            </div>

            <div class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-register-confirm-password">
                {{ $t("register.confirmPasswordPlaceholder") }}
              </label>
              <div class="tongdou-auth-input">
                <i class="el-icon-lock tongdou-auth-input__icon" aria-hidden="true"></i>
                <el-input id="tongdou-register-confirm-password" v-model="form.confirmPassword"
                  :placeholder="$t('register.confirmPasswordPlaceholder')" type="password"
                  autocomplete="new-password" show-password
                  @focus="handlePasswordFocus" @blur="handlePasswordBlur" />
              </div>
            </div>

            <div v-if="!enableMobileRegister" class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-register-captcha">
                {{ $t("register.captchaPlaceholder") }}
              </label>
              <div class="tongdou-auth-inline">
                <div class="tongdou-auth-input">
                  <i class="el-icon-key tongdou-auth-input__icon" aria-hidden="true"></i>
                  <el-input id="tongdou-register-captcha" v-model="form.captcha"
                    :placeholder="$t('register.captchaPlaceholder')" autocomplete="off" />
                </div>
                <img v-if="captchaUrl" class="tongdou-auth-captcha" :src="captchaUrl" alt="验证码"
                  @click="fetchCaptcha" />
              </div>
            </div>

            <div class="tongdou-auth-links">
              <button type="button" class="tongdou-auth-link" @click="goToLogin">
                {{ $t("register.goToLogin") }}
              </button>
            </div>

            <button type="submit" class="tongdou-auth-primary-button" :disabled="isSubmitting"
              @mousedown.prevent>
              <i v-if="isSubmitting" class="el-icon-loading" aria-hidden="true"></i>
              {{ $t("register.registerButton") }}
            </button>
          </form>

          <p class="tongdou-auth-agreement">
            {{ $t("register.agreeTo") }}
            <button type="button" class="tongdou-auth-link" @click="openPage('/user-agreement.html')">
              {{ $t("register.userAgreement") }}
            </button>
            {{ $t("login.and") }}
            <button type="button" class="tongdou-auth-link" @click="openPage('/privacy-policy.html')">
              {{ $t("register.privacyPolicy") }}
            </button>
          </p>
        </div>
      </section>
    </main>

    <footer class="tongdou-auth-footer">
      <version-footer product-mode />
    </footer>
  </div>
</template>

<script>
import Api from "@/apis/api";
import TongDouAuthVisual from "@/components/auth/TongDouAuthVisual.vue";
import VersionFooter from "@/components/VersionFooter.vue";
import i18n, { changeLanguage } from "@/i18n";
import { getUUID, goToPage, showDanger, showSuccess, sm2Encrypt, validateMobile } from "@/utils";
import { mapState } from "vuex";

export default {
  name: "register",
  components: {
    TongDouAuthVisual,
    VersionFooter,
  },
  computed: {
    ...mapState({
      allowUserRegister: (state) => state.pubConfig.allowUserRegister,
      enableMobileRegister: (state) => state.pubConfig.enableMobileRegister,
      mobileAreaList: (state) => state.pubConfig.mobileAreaList,
      sm2PublicKey: (state) => state.pubConfig.sm2PublicKey,
    }),
    currentLanguage() {
      return i18n.locale || "zh_CN";
    },
    currentLanguageText() {
      switch (this.currentLanguage) {
        case "zh_CN":
          return this.$t("language.zhCN");
        case "zh_TW":
          return this.$t("language.zhTW");
        case "en":
          return this.$t("language.en");
        case "de":
          return this.$t("language.de");
        case "vi":
          return this.$t("language.vi");
        case "pt_BR":
          return this.$t("language.ptBR");
        default:
          return this.$t("language.zhCN");
      }
    },
    formSubtitle() {
      return this.currentLanguage.startsWith("zh")
        ? "创建你的 TongDou 控制中心账号。"
        : "Create your TongDou Control Center account.";
    },
    canSendMobileCaptcha() {
      return this.countdown === 0 && validateMobile(this.form.mobile, this.form.areaCode);
    },
  },
  data() {
    return {
      form: {
        username: "",
        password: "",
        confirmPassword: "",
        captcha: "",
        captchaId: "",
        areaCode: "+86",
        mobile: "",
        mobileCaptcha: "",
      },
      captchaUrl: "",
      countdown: 0,
      timer: null,
      languageDropdownVisible: false,
      isSubmitting: false,
      authState: "boot",
    };
  },
  mounted() {
    this.$store.dispatch("fetchPubConfig").then(() => {
      if (!this.allowUserRegister) {
        showDanger(this.$t("register.notAllowRegister"));
        setTimeout(() => {
          goToPage("/login");
        }, 1500);
      }
    });
    this.fetchCaptcha();
  },
  methods: {
    openPage(url) {
      const lang = this.$i18n ? this.$i18n.locale : "zh_CN";
      if (!lang.startsWith("zh")) {
        url = url.replace(".html", "-en.html");
      }
      window.open(url, "_blank");
    },
    handleLanguageDropdownVisibleChange(visible) {
      this.languageDropdownVisible = visible;
    },
    changeLanguage(lang) {
      changeLanguage(lang);
      this.languageDropdownVisible = false;
      this.$message.success({
        message: this.$t("message.success"),
        showClose: true,
      });
    },
    handleIdentityFocus() {
      if (!this.isSubmitting) {
        this.authState = "look";
      }
    },
    handleIdentityBlur() {
      if (!this.isSubmitting) {
        this.authState = "idle";
      }
    },
    handlePasswordFocus() {
      if (!this.isSubmitting) {
        this.authState = "privacy";
      }
    },
    handlePasswordBlur() {
      if (!this.isSubmitting) {
        this.authState = "idle";
      }
    },
    fetchCaptcha() {
      this.form.captchaId = getUUID();
      Api.user.getCaptcha(this.form.captchaId, (res) => {
        if (res.status === 200) {
          const blob = new Blob([res.data], { type: res.data.type });
          this.captchaUrl = URL.createObjectURL(blob);
        } else {
          console.error("验证码加载异常:", error);
          showDanger(this.$t("register.captchaLoadFailed"));
        }
      });
    },
    validateInput(input, message) {
      if (!input.trim()) {
        showDanger(message);
        return false;
      }
      return true;
    },
    sendMobileCaptcha() {
      if (!validateMobile(this.form.mobile, this.form.areaCode)) {
        showDanger(this.$t("register.inputCorrectMobile"));
        return;
      }
      if (!this.validateInput(this.form.captcha, this.$t("register.inputCaptcha"))) {
        this.fetchCaptcha();
        return;
      }
      if (this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
      this.countdown = 60;
      this.timer = setInterval(() => {
        if (this.countdown > 0) {
          this.countdown--;
        } else {
          clearInterval(this.timer);
          this.timer = null;
        }
      }, 1000);

      Api.user.sendSmsVerification(
        {
          phone: this.form.areaCode + this.form.mobile,
          captcha: this.form.captcha,
          captchaId: this.form.captchaId,
        },
        () => {
          showSuccess(this.$t("register.captchaSendSuccess"));
        },
        (err) => {
          showDanger(err.data.msg || this.$t("register.captchaSendFailed"));
          this.countdown = 0;
          this.fetchCaptcha();
        }
      );
    },
    async register() {
      if (this.isSubmitting) {
        return;
      }

      if (this.enableMobileRegister) {
        if (!validateMobile(this.form.mobile, this.form.areaCode)) {
          showDanger(this.$t("register.inputCorrectMobile"));
          return;
        }
        if (!this.form.mobileCaptcha) {
          showDanger(this.$t("register.requiredMobileCaptcha"));
          return;
        }
      } else if (!this.validateInput(this.form.username, this.$t("register.requiredUsername"))) {
        return;
      }

      if (!this.validateInput(this.form.password, this.$t("register.requiredPassword"))) {
        return;
      }
      if (this.form.password !== this.form.confirmPassword) {
        showDanger(this.$t("register.passwordsNotMatch"));
        return;
      }
      if (!this.validateInput(this.form.captcha, this.$t("register.requiredCaptcha"))) {
        return;
      }

      let encryptedPassword;
      try {
        const captchaAndPassword = this.form.captcha + this.form.password;
        encryptedPassword = sm2Encrypt(this.sm2PublicKey, captchaAndPassword);
      } catch (error) {
        console.error("密码加密失败:", error);
        showDanger(this.$t("sm2.encryptionFailed"));
        return;
      }

      const plainUsername = this.enableMobileRegister
        ? this.form.areaCode + this.form.mobile
        : this.form.username;
      const registerData = {
        username: plainUsername,
        password: encryptedPassword,
        captchaId: this.form.captchaId,
        mobileCaptcha: this.form.mobileCaptcha,
      };

      this.isSubmitting = true;
      this.authState = "submitting";

      Api.user.register(
        registerData,
        () => {
          this.authState = "success";
          showSuccess(this.$t("register.registerSuccess"));
          goToPage("/login");
        },
        (err) => {
          this.isSubmitting = false;
          this.authState = "idle";
          showDanger(err.data.msg || this.$t("register.registerFailed"));
          if (err.data != null && err.data.msg != null && err.data.msg.indexOf("图形验证码") > -1) {
            this.fetchCaptcha();
          }
        }
      );
    },
    goToLogin() {
      goToPage("/login");
    },
  },
  beforeDestroy() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  },
};
</script>

<style lang="scss" scoped>
@import "./auth-tongdou.scss";
</style>
