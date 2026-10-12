#!/usr/bin/env python3
"""
anti提示词 · 六道强制出门闸门检查器
支持纯 Python 3 标准库，无需任何外部依赖。
用于检查生成视频提示词是否符合工业级标准（字数、图片限额、违禁管理词、台词时长等）。
"""

import sys
import re
import os

BANNED_CODE_TERMS = [
    "接下一大分镜",
    "接下一段",
    "承接下一段",
    "接分镜2",
    "无则删除",
    "未启用",
    "不继承上一场",
    "换场景后默认普通衔接",
    "不使用上一场",
    "如果没有则删除",
    "本段未启用",
    "全局控制：9:16",
    "全局控制：16:9",
]

def analyze_prompt_content(text):
    results = {
        "passed": True,
        "warnings": [],
        "errors": [],
        "metrics": {}
    }

    # 提取代码框内容
    code_blocks = re.findall(r"```(?:text|markdown)?\s*\n(.*?)\n```", text, re.DOTALL)
    # 如果存在多个代码块，优先识别包含视频提示词特征的块
    target_block = None
    if code_blocks:
        for block in code_blocks:
            if "镜头轨" in block or "特别注意" in block or "素材锚定" in block or "—— 通用后缀 ——" in block:
                target_block = block
                break
        if not target_block:
            target_block = code_blocks[0]
        pure_text = target_block
    else:
        pure_text = text

    char_count = len(pure_text)
    results["metrics"]["char_count"] = char_count

    # 闸门 1: 1900 字安全线 / 2000 字硬上限
    if char_count > 2000:
        results["errors"].append(f"[闸门1 失败] 提示词字数 ({char_count}字) 超出 2000 字平台硬上限！必须拆分单元或压缩。")
        results["passed"] = False
    elif char_count > 1900:
        results["warnings"].append(f"[闸门1 警告] 提示词字数 ({char_count}字) 处于 1901-2000 临界区，建议压缩至 1900 字内。")
    else:
        results["metrics"]["gate1_status"] = f"合格 ({char_count} <= 1900 字)"

    # 闸门 2: 单组图片上限 9 张
    img_refs = set(re.findall(r"@(图片\d+|Image\d+)", pure_text))
    img_count = len(img_refs)
    results["metrics"]["img_count"] = img_count
    results["metrics"]["img_refs"] = sorted(list(img_refs))
    if img_count > 9:
        results["errors"].append(f"[闸门2 失败] 单组引用的图片数量 ({img_count}张) 超过 9 张上限！涉及: {img_refs}")
        results["passed"] = False
    else:
        results["metrics"]["gate2_status"] = f"合格 ({img_count} <= 9 张)"

    # 闸门 3: 可投喂语义与违禁管理词
    found_banned = []
    for term in BANNED_CODE_TERMS:
        if term in pure_text:
            found_banned.append(term)
    if found_banned:
        results["errors"].append(f"[闸门3 失败] 发现模型无法执行的流程管理违禁词: {found_banned}")
        results["passed"] = False
    else:
        results["metrics"]["gate3_status"] = "合格 (无违禁管理词)"

    # 闸门 4: 必备视听控制项 (模板 C / A 结构)
    required_sections = ["素材锚定", "镜头轨", "声音轨", "硬锁", "段末状态"]
    missing_sections = [s for s in required_sections if s not in pure_text]
    if missing_sections and "【分镜 1】" not in pure_text:
        results["warnings"].append(f"[闸门4 提醒] 提示词可能缺少模板 C 核心字段: {missing_sections}")
    else:
        results["metrics"]["gate4_status"] = "合格 (结构完整)"

    # 闸门 5: 台词与语速估算
    dialogues = re.findall(r'[“"「]([^“”"」]{2,})[”"」]', pure_text)
    total_dialogue_chars = sum(len(d) for d in dialogues)
    results["metrics"]["dialogue_chars"] = total_dialogue_chars
    if total_dialogue_chars > 0:
        est_min_seconds = round(total_dialogue_chars / 5.0 + 1.0, 1)
        results["metrics"]["est_dialogue_duration"] = f"约需 {est_min_seconds} 秒 (按5字/秒加停顿)"
        if est_min_seconds > 15:
            results["warnings"].append(f"[闸门5 警告] 本段台词字数 ({total_dialogue_chars}字) 预计需要 {est_min_seconds}s，超过单段 15 秒上限，建议拆分！")

    return results

def main():
    if len(sys.argv) < 2:
        print("用法: python3 check_prompt_gates.py <提示词文件路径>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在 {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"=== anti提示词 六道出门闸门自检: {os.path.basename(file_path)} ===")
    res = analyze_prompt_content(content)

    print("\n【核心指标】")
    for k, v in res["metrics"].items():
        print(f"- {k}: {v}")

    if res["warnings"]:
        print("\n【⚠️ 警告项】")
        for w in res["warnings"]:
            print(f"  {w}")

    if res["errors"]:
        print("\n【❌ 错误项】")
        for e in res["errors"]:
            print(f"  {e}")

    print("\n" + ("="*40))
    if res["passed"]:
        print("✅ 检查通过！符合工业级投喂标准。")
        sys.exit(0)
    else:
        print("❌ 检查未通过，请根据上述错误项修改。")
        sys.exit(1)

if __name__ == "__main__":
    main()
