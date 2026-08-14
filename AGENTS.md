# 工作约定：GitHub 自动同步

本仓库已连接 GitHub：远端 `origin` 指向 `https://github.com/MyHeartBea/selfstudy.git`，默认分支 `main`，登录已由 Git Credential Manager 记住。

## 规则

1. 每次完成代码、数据或文档修改并验证通过后，自动提交并推送到 GitHub，除非用户明确要求“先不要提交/推送”。
2. 提交命令固定使用：

   ```powershell
   git add -A
   git commit -m "本次改动的简短说明"
   git push
   ```

3. 提交前检查 `.gitignore`，确保 `.env`、数据库文件、构建产物、浏览器缓存等敏感或临时文件不会被推送。
4. 推送后确认 `main` 与 `origin/main` 一致；若推送失败，说明原因并尝试解决后再继续。
5. **C 盘空间紧张（约剩 1.5GB）**：所有临时文件、缓存、下载、中间产物一律放 D 盘
   （临时/探测文件放 `D:\temp`），不要写 C 盘（含 `%TEMP%`、`~/.cache` 等位置）。
