# 安全配置指南

## ⚠️ 重要安全说明

本项目包含敏感的配置信息，请严格按照以下步骤进行安全配置。

## 🔧 配置步骤

### 1. 创建本地配置文件

复制配置模板并填入真实信息：

```bash
# 根目录配置
cp config.yaml.example config.yaml

# AITrade_MT5目录配置（如果使用）
cp AITrade_MT5/config.yaml.example AITrade_MT5/config.yaml
```

### 2. 填写配置信息

编辑 `config.yaml` 文件，替换以下占位符：

- `base_url`: 您的AI服务商API地址
- `api_key`: 您的真实API密钥（格式：sk-xxxxxxxxx）
- `model_id`: AI模型名称
- `mt5_account`（可选）: MT5账户信息

### 3. 配置文件示例

```yaml
ai:
  base_url: "https://your-ai-service.com/v1"
  api_key: "sk-YOUR_REAL_API_KEY_HERE"
  model_id: "gpt-4"
```

## 🛡️ 安全最佳实践

1. **永远不要提交 `config.yaml` 到版本控制**
   - `.gitignore` 已配置排除此文件
   - 只提交 `config.yaml.example` 模板

2. **定期轮换API密钥**
   - 建议每月更换API密钥
   - 发现泄露时立即更换

3. **使用环境变量（推荐）**
   - 敏感信息可通过环境变量传递
   - 避免在文件中存储真实密钥

4. **权限控制**
   - 设置配置文件权限：`chmod 600 config.yaml`
   - 仅允许必要用户访问

## 🚨 泄露应急处理

如果怀疑API密钥泄露：

1. **立即撤销密钥**：联系AI服务商撤销当前密钥
2. **生成新密钥**：创建新的API密钥
3. **更新本地配置**：替换配置文件中的密钥
4. **检查Git历史**：确保没有提交过敏感信息

## 📝 联系方式

如有安全问题，请通过私密渠道联系项目维护者。