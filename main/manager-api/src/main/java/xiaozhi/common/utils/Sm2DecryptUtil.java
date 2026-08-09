package xiaozhi.common.utils;

import org.apache.commons.lang3.StringUtils;
import xiaozhi.common.constant.Constant;
import xiaozhi.common.exception.ErrorCode;
import xiaozhi.common.exception.RenException;
import xiaozhi.modules.security.service.CaptchaService;
import xiaozhi.modules.sys.service.SysParamsService;

/**
 * SM2 decrypt and captcha validation helper.
 */
public class Sm2DecryptUtil {

    private static final int CAPTCHA_LENGTH = 5;

    public static String decryptAndValidateCaptcha(String encryptedPassword, String captchaId,
            CaptchaService captchaService, SysParamsService sysParamsService) {
        return decryptPassword(encryptedPassword, captchaId, captchaService, sysParamsService, true);
    }

    public static String decryptLoginPassword(String encryptedPassword, String captchaId,
            CaptchaService captchaService, SysParamsService sysParamsService) {
        String loginCaptchaEnabled = sysParamsService.getValue(Constant.SERVER_LOGIN_CAPTCHA_ENABLED, true);
        boolean validateCaptcha = !"false".equalsIgnoreCase(loginCaptchaEnabled);
        return decryptPassword(encryptedPassword, captchaId, captchaService, sysParamsService, validateCaptcha);
    }

    private static String decryptPassword(String encryptedPassword, String captchaId,
            CaptchaService captchaService, SysParamsService sysParamsService, boolean validateCaptcha) {
        String privateKeyStr = sysParamsService.getValue(Constant.SM2_PRIVATE_KEY, true);
        if (StringUtils.isBlank(privateKeyStr)) {
            throw new RenException(ErrorCode.SM2_KEY_NOT_CONFIGURED);
        }

        String decryptedContent;
        try {
            decryptedContent = SM2Utils.decrypt(privateKeyStr, encryptedPassword);
        } catch (Exception e) {
            throw new RenException(ErrorCode.SM2_DECRYPT_ERROR);
        }

        if (!validateCaptcha) {
            if (StringUtils.isBlank(decryptedContent)) {
                throw new RenException(ErrorCode.SM2_DECRYPT_ERROR);
            }
            return decryptedContent;
        }

        if (decryptedContent.length() > CAPTCHA_LENGTH) {
            String embeddedCaptcha = decryptedContent.substring(0, CAPTCHA_LENGTH);
            String actualPassword = decryptedContent.substring(CAPTCHA_LENGTH);

            boolean embeddedCaptchaValid = captchaService.validate(captchaId, embeddedCaptcha, true);
            if (!embeddedCaptchaValid) {
                throw new RenException(ErrorCode.SMS_CAPTCHA_ERROR);
            }

            return actualPassword;
        } else if (decryptedContent.length() > 0) {
            throw new RenException(ErrorCode.SMS_CAPTCHA_ERROR);
        } else {
            throw new RenException(ErrorCode.SM2_DECRYPT_ERROR);
        }
    }
}
