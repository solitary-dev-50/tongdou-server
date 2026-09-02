<template>
  <div class="tongdou-auth-page">
    <main class="tongdou-auth-shell">
      <tong-dou-auth-visual ref="authVisual" :state="authState" mode="login" :locale="currentLanguage" />

      <section class="tongdou-auth-panel" aria-labelledby="login-title">
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
            <div class="tongdou-auth-heading__eyebrow">SYSTEM ACCESS</div>
            <h1 id="login-title">{{ $t("login.title") }}</h1>
            <p>{{ formSubtitle }}</p>
          </header>

          <form class="tongdou-auth-form" @submit.prevent="login">
            <div v-if="!isMobileLogin" class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-login-username">
                {{ $t("login.usernamePlaceholder") }}
              </label>
              <div class="tongdou-auth-input">
                <i class="el-icon-user tongdou-auth-input__icon" aria-hidden="true"></i>
                <el-input id="tongdou-login-username" v-model="form.username"
                  :placeholder="$t('login.usernamePlaceholder')" autocomplete="username"
                  @focus="handleIdentityFocus" @blur="handleIdentityBlur" />
              </div>
            </div>

            <div v-else class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-login-mobile">
                {{ $t("login.mobilePlaceholder") }}
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
                  <el-input id="tongdou-login-mobile" v-model="form.mobile"
                    :placeholder="$t('login.mobilePlaceholder')" autocomplete="tel" inputmode="tel"
                    @focus="handleIdentityFocus" @blur="handleIdentityBlur" />
                </div>
              </div>
            </div>

            <div class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-login-password">
                {{ $t("login.passwordPlaceholder") }}
              </label>
              <div class="tongdou-auth-input">
                <i class="el-icon-lock tongdou-auth-input__icon" aria-hidden="true"></i>
                <el-input id="tongdou-login-password" v-model="form.password"
                  :placeholder="$t('login.passwordPlaceholder')" type="password"
                  autocomplete="current-password" show-password
                  @focus="handlePasswordFocus" @blur="handlePasswordBlur" />
              </div>
            </div>

            <div v-if="loginCaptchaEnabled" class="tongdou-auth-field">
              <label class="tongdou-auth-field__label" for="tongdou-login-captcha">
                {{ $t("login.captchaPlaceholder") }}
              </label>
              <div class="tongdou-auth-inline">
                <div class="tongdou-auth-input">
                  <i class="el-icon-key tongdou-auth-input__icon" aria-hidden="true"></i>
                  <el-input id="tongdou-login-captcha" v-model="form.captcha"
                    :placeholder="$t('login.captchaPlaceholder')" autocomplete="off" />
                </div>
                <img v-if="captchaUrl" class="tongdou-auth-captcha" :src="captchaUrl" alt="验证码"
                  @click="fetchCaptcha" />
              </div>
            </div>

            <div class="tongdou-auth-links">
              <button v-if="allowUserRegister" type="button" class="tongdou-auth-link" @click="goToRegister">
                {{ $t("login.register") }}
              </button>
              <button v-if="enableMobileRegister" type="button" class="tongdou-auth-link"
                @click="goToForgetPassword">
                {{ $t("login.forgetPassword") }}
              </button>
            </div>

            <button type="submit" class="tongdou-auth-primary-button" :disabled="isSubmitting"
              @mousedown.prevent>
              <i v-if="isSubmitting" class="el-icon-loading" aria-hidden="true"></i>
              {{ $t("login.login") }}
            </button>

            <div v-if="enableMobileRegister" class="tongdou-auth-login-types" aria-label="Login method">
              <button type="button" :class="{ 'is-active': isMobileLogin }"
                :title="$t('login.mobileLogin')" @click="switchLoginType('mobile')">
                <i class="el-icon-mobile-phone" aria-hidden="true"></i>
              </button>
              <button type="button" :class="{ 'is-active': !isMobileLogin }"
                :title="$t('login.usernameLogin')" @click="switchLoginType('username')">
                <i class="el-icon-user" aria-hidden="true"></i>
              </button>
            </div>
          </form>

          <p class="tongdou-auth-agreement">
            {{ $t("login.agreeTo") }}
            <button type="button" class="tongdou-auth-link" @click="openPage('/user-agreement.html')">
              {{ $t("login.userAgreement") }}
            </button>
            {{ $t("login.and") }}
            <button type="button" class="tongdou-auth-link" @click="openPage('/privacy-policy.html')">
              {{ $t("login.privacyPolicy") }}
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
  name: "login",
  components: {
    TongDouAuthVisual,
    VersionFooter,
  },
  computed: {
    ...mapState({
      allowUserRegister: (state) => state.pubConfig.allowUserRegister,
      enableMobileRegister: (state) => state.pubConfig.enableMobileRegister,
      loginCaptchaEnabled: (state) => state.pubConfig.loginCaptchaEnabled !== false,
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
        ? "铜豆在这里看守服务器。请验证你的身份。"
        : "TongDou is guarding the server. Verify your identity.";
    },
  },
  data() {
    return {
      activeName: "username",
      form: {
        username: "",
        password: "",
        captcha: "",
        captchaId: "",
        areaCode: "+86",
        mobile: "",
      },
      captchaUuid: "",
      captchaUrl: "",
      isMobileLogin: false,
      languageDropdownVisible: false,
      isSubmitting: false,
      authState: "boot",
      suspiciousTimer: null,
    };
  },
  mounted() {
    this.$store.dispatch("fetchPubConfig").then(() => {
      this.isMobileLogin = this.enableMobileRegister;
      if (this.loginCaptchaEnabled) {
        this.fetchCaptcha();
      }
    });
  },
  beforeDestroy() {
    clearTimeout(this.suspiciousTimer);
  },
  methods: {
    openPage(url) {
      const lang = this.$i18n ? this.$i18n.locale : "zh_CN";
      if (!lang.startsWith("zh")) {
        url = url.replace(".html", "-en.html");
      }
      window.open(url, "_blank");
    },
    fetchCaptcha() {
      const token = localStorage.getItem("token");
      if (token) {
        if (this.$route.path !== "/home") {
          this.$router.push("/home");
        }
      } else {
        this.captchaUuid = getUUID();
        Api.user.getCaptcha(this.captchaUuid, (res) => {
          if (res.status === 200) {
            const blob = new Blob([res.data], { type: res.data.type });
            this.captchaUrl = URL.createObjectURL(blob);
          } else {
            showDanger("验证码加载失败，点击刷新");
          }
        });
      }
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
    switchLoginType(type) {
      this.isMobileLogin = type === "mobile";
      this.form.username = "";
      this.form.mobile = "";
      this.form.password = "";
      this.form.captcha = "";
      this.authState = "idle";
      if (this.loginCaptchaEnabled) {
        this.fetchCaptcha();
      }
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
    validateInput(input, messageKey) {
      if (!input.trim()) {
        showDanger(this.$t(messageKey));
        return false;
      }
      return true;
    },
    getUserInfo() {
      Api.user.getUserInfo(({ data }) => {
        if (data.code === 0) {
          this.$store.commit("setUserInfo", data.data);
          goToPage("/home");
        } else {
          this.isSubmitting = false;
          this.authState = "idle";
          showDanger("用户信息获取失败");
        }
      });
    },
    async login() {
      if (this.isSubmitting) {
        return;
      }

      if (this.isMobileLogin) {
        if (!validateMobile(this.form.mobile, this.form.areaCode)) {
          showDanger(this.$t("login.requiredMobile"));
          return;
        }
        this.form.username = this.form.areaCode + this.form.mobile;
      } else if (!this.validateInput(this.form.username, "login.requiredUsername")) {
        return;
      }

      if (!this.validateInput(this.form.password, "login.requiredPassword")) {
        return;
      }
      if (this.loginCaptchaEnabled && !this.validateInput(this.form.captcha, "login.requiredCaptcha")) {
        return;
      }

      let encryptedPassword;
      try {
        const captchaAndPassword = this.loginCaptchaEnabled
          ? this.form.captcha + this.form.password
          : this.form.password;
        encryptedPassword = sm2Encrypt(this.sm2PublicKey, captchaAndPassword);
      } catch (error) {
        console.error("密码加密失败:", error);
        showDanger(this.$t("sm2.encryptionFailed"));
        return;
      }

      const plainUsername = this.form.username;
      this.form.captchaId = this.loginCaptchaEnabled ? this.captchaUuid : "";
      const loginData = {
        username: plainUsername,
        password: encryptedPassword,
        captchaId: this.form.captchaId,
      };

      this.isSubmitting = true;
      this.authState = "submitting";

      Api.user.login(
        loginData,
        ({ data }) => {
          this.authState = "success";
          showSuccess(this.$t("login.loginSuccess"));
          this.$store.commit("setToken", JSON.stringify(data.data));
          this.getUserInfo();
        },
        (err) => {
          this.isSubmitting = false;
          const errorMessage = (err.data && err.data.msg) || "登录失败";
          const isAccountPasswordError = Number(err.data && err.data.code) === 10004;
          this.authState = isAccountPasswordError ? "suspicious" : "idle";
          showDanger(errorMessage);

          if (isAccountPasswordError) {
            clearTimeout(this.suspiciousTimer);
            this.suspiciousTimer = setTimeout(() => {
              if (!this.isSubmitting) {
                this.authState = "idle";
              }
            }, 1700);
          }
        }
      );

      setTimeout(() => {
        this.fetchCaptcha();
      }, 1000);
    },
    goToRegister() {
      goToPage("/register");
    },
    goToForgetPassword() {
      goToPage("/retrieve-password");
    },
  },
};
</script>

<style lang="scss" scoped>
@import "./auth-tongdou.scss";
</style>
