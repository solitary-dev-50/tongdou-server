-- 将未配置的 PowerMem 默认值切换为智谱低成本方案。
-- 只更新仍使用占位密钥的记录，避免覆盖管理员已经保存的真实配置。
UPDATE `ai_model_config`
SET `config_json` = '{"type":"powermem","enable_user_profile":true,"llm_provider":"openai","llm_api_key":"你的智谱API密钥","llm_model":"glm-4.7-flash","openai_base_url":"https://open.bigmodel.cn/api/paas/v4/","embedding_provider":"openai","embedding_api_key":"你的智谱API密钥","embedding_model":"embedding-3","embedding_openai_base_url":"https://open.bigmodel.cn/api/paas/v4/","embedding_dims":2048,"vector_store":{"provider":"sqlite","config":{}}}'
WHERE `id` = 'Memory_powermem'
  AND JSON_UNQUOTE(JSON_EXTRACT(`config_json`, '$.llm_api_key')) = '你的LLM API密钥';

UPDATE `ai_model_config`
SET `remark` = '【推荐：近零成本配置】
PowerMem和SQLite本身免费；glm-4.7-flash当前为智谱免费模型；embedding-3按智谱实际价格计费。

【配置值】
- enable_user_profile: true
- llm_provider: openai
- llm_model: glm-4.7-flash
- openai_base_url: https://open.bigmodel.cn/api/paas/v4/
- embedding_provider: openai
- embedding_model: embedding-3
- embedding_openai_base_url: https://open.bigmodel.cn/api/paas/v4/
- embedding_dims: 2048
- vector_store: {"provider":"sqlite","config":{}}

大语言模型和向量模型可使用同一个智谱API密钥。请在后台填写真实密钥，不要把密钥提交到代码仓库。

注意：当前铜豆接入按设备编号隔离记忆，同一设备上的多位说话人暂未分开。'
WHERE `id` = 'Memory_powermem';
