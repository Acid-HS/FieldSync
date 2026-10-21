import subprocess
import os
import re
from datetime import datetime

# ============ 配置 ============
COMMANDS = [
    ("rapx", "cargo +nightly-2025-12-06 rapx check -f"),
    ("safedrop", "rustc +safedrop src/main.rs"),
    ("charon_rudra", "charon --ullbc && cargo-charon-rudra --file test_tools.ullbc"),
    ("miri", "cargo +nightly miri run"),
    ("kani", "cargo kani --output-format terse"),
]

CASE_DIR       = "case"
SRC_MAIN       = "src/main.rs"
CARGO_TOML     = "Cargo.toml"
INDIVIDUAL_LOG = "individual_report.log"
AGGREGATE_LOG  = "aggregate_report.log"

CARGO_FEATURES_LINE = 'cargo-features = ["edition2024"]\n'

COLOR_CODE_MAP = {
    "30": "Black", "31": "Red", "32": "Green", "33": "Yellow",
    "34": "Blue", "35": "Magenta", "36": "Cyan", "37": "White",
    "90": "BrightBlack", "91": "BrightRed", "92": "BrightGreen",
    "93": "BrightYellow", "94": "BrightBlue", "95": "BrightMagenta",
    "96": "BrightCyan", "97": "BrightWhite",
}

SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
CSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def extract_colors(line):
    sgr = SGR_RE.findall(line)
    if not sgr:
        return False, CSI_RE.sub("", line), []
    names = []
    for params in sgr:
        for tok in params.split(";"):
            cname = COLOR_CODE_MAP.get(tok)
            if cname and cname not in names:
                names.append(cname)
    return True, CSI_RE.sub("", line), names


# ============ RAPX 重复报错合并 ============
def parse_rapx_warnings(text):
    cleaned = CSI_RE.sub("", text)
    blocks = re.split(
        r"(?=^warning:\s*(?:double\s*free|use[- ]?after[- ]?free))",
        cleaned,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    merged = {}
    for block in blocks:
        if not re.match(r"^\s*warning:", block):
            continue
        title_match = re.match(r"\s*warning:\s*(.*)", block)
        if not title_match:
            continue
        title = title_match.group(1).strip()

        if re.search(r"double\s*free", title, re.IGNORECASE):
            wtype = "Double Free"
        elif re.search(r"use[- ]?after[- ]?free", title, re.IGNORECASE):
            wtype = "Use-After-Free"
        else:
            continue

        loc = re.search(r"-->\s*(\S+):(\d+):(\d+)", block)
        if not loc:
            continue
        file, line, _col = loc.groups()

        key = (wtype, file, line)
        if key not in merged:
            merged[key] = {
                "type": wtype,
                "file": file,
                "line": line,
                "confidences": set(),
                "mir_details": [],
            }

        for c in re.findall(
            r"(?:double\s*free|use[- ]?after[- ]?free)\s*\(confidence\s*(\d+)%\)",
            block, re.IGNORECASE
        ):
            merged[key]["confidences"].add(int(c))

        for d in re.findall(r"MIR detail:\s*(.*)", block):
            d = d.strip()
            if d and d not in merged[key]["mir_details"]:
                merged[key]["mir_details"].append(d)

    result = []
    for key, v in merged.items():
        result.append({
            "type": v["type"],
            "file": v["file"],
            "line": v["line"],
            "confidences": sorted(v["confidences"], reverse=True),
            "mir_details": v["mir_details"],
        })
    result.sort(key=lambda x: (x["type"], x["file"], int(x["line"])))
    return result


# ============ Miri 错误解析 ============
def parse_miri_errors(text):
    cleaned = CSI_RE.sub("", text)
    errors = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        m = re.match(r"^error(?:\[[^\]]*\])?:\s*(.*)$", stripped)
        if not m:
            continue
        desc = m.group(1).strip()
        if re.match(r"aborting due to", desc, re.IGNORECASE):
            continue
        errors.append(desc)

    ub_errors = [d for d in errors if d.lower().startswith("undefined behavior")]
    return {
        "total_errors": len(errors),
        "ub_errors": len(ub_errors),
        "details": errors,
    }


# ============ 执行全部工具 ============
def run_experiment():
    outputs = {}
    for name, cmd in COMMANDS:
        print(f"    [*] Executing {name}...")

        cargo_backup = None
        backup_content = None
        try:
            # --- charon_rudra：临时注入 cargo-features ---
            if name == "charon_rudra":
                if os.path.exists(CARGO_TOML):
                    with open(CARGO_TOML, "r") as f:
                        cargo_backup = f.read()
                    # 若已存在 cargo-features 行则不再注入
                    if not cargo_backup.lstrip().startswith("cargo-features"):
                        with open(CARGO_TOML, "w") as f:
                            f.write(CARGO_FEATURES_LINE + cargo_backup)
                        print("    [+] Injected cargo-features line into Cargo.toml")
                    else:
                        cargo_backup = None  # 本来就有，无需还原
                else:
                    print(f"    [!] {CARGO_TOML} not found, charon_rudra may fail.")

            # --- Kani 特殊处理：注入代码 ---
            if name == "kani":
                if os.path.exists(SRC_MAIN):
                    with open(SRC_MAIN, "r") as f:
                        backup_content = f.read()
                    with open(SRC_MAIN, "a") as f:
                        f.write("\n\n#[cfg(kani)]\n#[kani::proof]\nfn kani_harness() { main(); }\n")
                else:
                    print(f"    [!] {SRC_MAIN} not found, skipping Kani.")
                    outputs[name] = {"stdout": "", "stderr": f"{SRC_MAIN} not found"}
                    continue

            # --- 执行命令 ---
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                    text=True, env=env)
            outputs[name] = {"stdout": result.stdout, "stderr": result.stderr}

            # --- Kani harness 还原 ---
            if name == "kani" and backup_content is not None:
                with open(SRC_MAIN, "w") as f:
                    f.write(backup_content)
                print("    [~] Kani harness removed, src/main.rs restored.")

            subprocess.run("cargo clean", shell=True, capture_output=True)
            if os.path.exists("sf_test.ullbc"):
                os.remove("sf_test.ullbc")
        finally:
            # --- charon_rudra：还原 Cargo.toml ---
            if cargo_backup is not None:
                with open(CARGO_TOML, "w") as f:
                    f.write(cargo_backup)
                print("    [~] Cargo.toml restored.")
    return outputs


def format_raw_outputs(outputs):
    parts = [f"=== EXPERIMENT LOG: {datetime.now()} ==="]
    for name, _ in COMMANDS:
        if name not in outputs:
            continue
        parts.append(f"[[TOOL_START: {name}]]")
        parts.append(f"STDOUT:\n{outputs[name]['stdout']}")
        parts.append(f"STDERR:\n{outputs[name]['stderr']}")
        parts.append(f"[[TOOL_END: {name}]]")
    return "\n".join(parts) + "\n"


# ============ 单用例分析 ============
def analyze_from_outputs(outputs):
    report_lines = ["\n" + "=" * 60,
                    "### INDIVIDUAL TOOL ANALYSIS REPORT ###",
                    "=" * 60 + "\n"]
    metrics = {
        "rapx": {"double_free": 0, "use_after_free": 0, "items": []},
        "safedrop": {"double_free": 0, "use_after_free": 0},
        "charon_rudra": {"color_counts": {}, "highlighted": []},
        "kani": {"failed_checks": 0, "failures": []},
        "miri": {"total_errors": 0, "ub_errors": 0, "details": []},
    }

    for name, _ in COMMANDS:
        if name not in outputs:
            continue
        block_text = outputs[name]["stdout"] + "\n" + outputs[name]["stderr"]
        tool_report = [f"[{name.upper()}]:"]

        if name == "rapx":
            merged_items = parse_rapx_warnings(block_text)
            df = sum(1 for it in merged_items if it["type"] == "Double Free")
            uaf = sum(1 for it in merged_items if it["type"] == "Use-After-Free")
            metrics["rapx"] = {"double_free": df, "use_after_free": uaf,
                               "items": merged_items}

            tool_report.append(f"  - Double Free (unique locations): {df}")
            tool_report.append(f"  - Use-After-Free (unique locations): {uaf}")
            if merged_items:
                tool_report.append("  - Detailed issues (duplicates merged by location):")
                for it in merged_items:
                    conf = (", ".join(f"{c}%" for c in it["confidences"])
                            if it["confidences"] else "N/A")
                    tool_report.append(
                        f"    * {it['type']} (confidence {conf}) "
                        f"at {it['file']}:{it['line']}"
                    )
                    for d in it["mir_details"]:
                        tool_report.append(f"      - MIR detail: {d}")
            else:
                tool_report.append("  - Detailed issues: (none)")

        elif name == "safedrop":
            df_match = re.search(r"Double Free Bugs Exist:\n(.*?)(?=\n\n|\n[A-Z]|$)",
                                 block_text, re.DOTALL)
            df_count = len(re.findall(r"occurs in", df_match.group(1))) if df_match else 0
            uaf_match = re.search(r"Use After Free Bugs Exist:\n(.*?)(?=\n\n|\n[A-Z]|$)",
                                  block_text, re.DOTALL)
            uaf_count = len(re.findall(r"occurs in", uaf_match.group(1))) if uaf_match else 0
            metrics["safedrop"] = {"double_free": df_count, "use_after_free": uaf_count}
            tool_report.append(f"  - Double Free (occurs lines): {df_count}")
            tool_report.append(f"  - Use After Free (occurs lines): {uaf_count}")

        elif name == "charon_rudra":
            color_counts = {}
            for params in SGR_RE.findall(block_text):
                for tok in params.split(";"):
                    cname = COLOR_CODE_MAP.get(tok)
                    if cname:
                        color_counts[cname] = color_counts.get(cname, 0) + 1
            metrics["charon_rudra"]["color_counts"] = color_counts

            if color_counts:
                tool_report.append("  - Colored Output Statistics:")
                for c in sorted(color_counts):
                    tool_report.append(f"    * {c}: {color_counts[c]} tags")
            else:
                tool_report.append("  - No color tags found.")

            highlighted, seen = [], set()
            for line in block_text.splitlines():
                has_sgr, plain, colors = extract_colors(line)
                if not has_sgr:
                    continue
                plain = plain.strip()
                if not plain or plain in seen:
                    continue
                seen.add(plain)
                tag = ", ".join(colors) if colors else "Styled"
                highlighted.append((tag, plain))
            metrics["charon_rudra"]["highlighted"] = highlighted

            if highlighted:
                tool_report.append(
                    f"  - Highlighted Statements ({len(highlighted)} unique):"
                )
                for tag, text in highlighted:
                    tool_report.append(f"    * [{tag}] {text}")
            else:
                tool_report.append("  - Highlighted Statements: (none)")

        elif name == "kani":
            failures = re.findall(
                r"Failed Checks: (.*?)\n File: \"(.*?)\", line (\d+)",
                block_text
            )
            failures = [
                f for f in failures
                if "unused" not in f[0].lower()
                and not f[0].lower().startswith("warning")
            ]
            metrics["kani"] = {"failed_checks": len(failures), "failures": failures}
            tool_report.append(f"  - Total Failed Checks: {len(failures)}")
            for desc, fpath, line in failures:
                tool_report.append(f"    * {desc} at {fpath}:{line}")

        elif name == "miri":
            miri_stat = parse_miri_errors(block_text)
            metrics["miri"] = miri_stat
            tool_report.append(f"  - Total errors: {miri_stat['total_errors']}")
            tool_report.append(f"  - Undefined Behavior errors: {miri_stat['ub_errors']}")
            if miri_stat["details"]:
                tool_report.append("  - Error details:")
                for d in miri_stat["details"]:
                    tool_report.append(f"    * {d}")
            else:
                tool_report.append("  - Error details: (none)")

        report_lines.append("\n".join(tool_report))

    return "\n".join(report_lines), metrics


def run_single_case(case_path, case_name):
    with open(case_path, "r") as f:
        case_content = f.read()
    with open(SRC_MAIN, "w") as f:
        f.write(case_content)

    outputs = run_experiment()
    raw_text = format_raw_outputs(outputs)
    report_str, metrics = analyze_from_outputs(outputs)

    section = (
        f"\n{'#' * 70}\n"
        f"# CASE: {case_name}\n"
        f"{'#' * 70}\n\n"
        f"{raw_text}\n"
        f"{report_str}\n"
    )
    return section, metrics


# ============ 跨用例汇总 ============
def merge_metrics(metrics_list):
    merged = {
        "rapx": {"double_free": 0, "use_after_free": 0},
        "safedrop": {"double_free": 0, "use_after_free": 0},
        "charon_rudra": {"color_counts": {}, "highlighted": []},
        "kani": {"failed_checks": 0, "failures": []},
        "miri": {"total_errors": 0, "ub_errors": 0, "details": []},
    }
    seen_hl, seen_fail, seen_miri = set(), set(), set()
    for m in metrics_list:
        merged["rapx"]["double_free"] += m["rapx"]["double_free"]
        merged["rapx"]["use_after_free"] += m["rapx"]["use_after_free"]
        merged["safedrop"]["double_free"] += m["safedrop"]["double_free"]
        merged["safedrop"]["use_after_free"] += m["safedrop"]["use_after_free"]

        for c, n in m["charon_rudra"]["color_counts"].items():
            merged["charon_rudra"]["color_counts"][c] = \
                merged["charon_rudra"]["color_counts"].get(c, 0) + n
        for tag, text in m["charon_rudra"]["highlighted"]:
            if text not in seen_hl:
                seen_hl.add(text)
                merged["charon_rudra"]["highlighted"].append((tag, text))

        merged["kani"]["failed_checks"] += m["kani"]["failed_checks"]
        for f in m["kani"]["failures"]:
            key = tuple(f)
            if key not in seen_fail:
                seen_fail.add(key)
                merged["kani"]["failures"].append(f)

        merged["miri"]["total_errors"] += m["miri"]["total_errors"]
        merged["miri"]["ub_errors"] += m["miri"]["ub_errors"]
        for d in m["miri"]["details"]:
            if d not in seen_miri:
                seen_miri.add(d)
                merged["miri"]["details"].append(d)
    return merged


def format_aggregate(merged, title, ok_names, fail_names):
    lines = ["=" * 70, f"### {title} ###", "=" * 70, ""]
    lines.append(f"Successful cases ({len(ok_names)}): "
                 f"{', '.join(ok_names) if ok_names else '(none)'}")
    if fail_names:
        lines.append(f"Failed cases ({len(fail_names)}): {', '.join(fail_names)}")
    lines.append("")

    if not ok_names and not fail_names:
        lines.append("(no cases in this group)")
        return "\n".join(lines)

    lines.append("[RAPX]:")
    lines.append(f"  - Double Free (unique locations): {merged['rapx']['double_free']}")
    lines.append(f"  - Use-After-Free (unique locations): {merged['rapx']['use_after_free']}")
    lines.append("")

    lines.append("[SAFEDROP]:")
    lines.append(f"  - Double Free (occurs lines): {merged['safedrop']['double_free']}")
    lines.append(f"  - Use After Free (occurs lines): {merged['safedrop']['use_after_free']}")
    lines.append("")

    lines.append("[CHARON_RUDRA]:")
    cc = merged["charon_rudra"]["color_counts"]
    if cc:
        lines.append("  - Color tag totals:")
        for c in sorted(cc):
            lines.append(f"    * {c}: {cc[c]}")
    else:
        lines.append("  - No color tags found.")
    hs = merged["charon_rudra"]["highlighted"]
    if hs:
        for tag, text in hs:
            lines.append(f"    * [{tag}] {text}")
    else:
        lines.append("  - (no highlighted statements)")
    lines.append("")

    lines.append("[KANI]:")
    lines.append(f"  - Total Failed Checks: {merged['kani']['failed_checks']}")
    for desc, fpath, line in merged["kani"]["failures"]:
        lines.append(f"    * {desc} at {fpath}:{line}")
    lines.append("")

    lines.append("[MIRI]:")
    lines.append(f"  - Total errors: {merged['miri']['total_errors']}")
    lines.append(f"  - Undefined Behavior errors: {merged['miri']['ub_errors']}")
    if merged["miri"]["details"]:
        lines.append("  - Error details:")
        for d in merged["miri"]["details"]:
            lines.append(f"    * {d}")
    else:
        lines.append("  - Error details: (none)")

    return "\n".join(lines)


# ============ 主流程 ============
def _natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def main():
    if not os.path.isdir(CASE_DIR):
        print(f"[!] {CASE_DIR}/ not found")
        return
    os.makedirs(os.path.dirname(SRC_MAIN) or ".", exist_ok=True)

    case_files = sorted(
        (f for f in os.listdir(CASE_DIR) if f.endswith(".rs")),
        key=_natural_key
    )
    if not case_files:
        print(f"[!] No .rs files in {CASE_DIR}/")
        return

    original_main = None
    if os.path.exists(SRC_MAIN):
        with open(SRC_MAIN, "r") as f:
            original_main = f.read()

    individual_sections = []
    groups = {
        "1": {"metrics": [], "ok": [], "fail": []},
        "2": {"metrics": [], "ok": [], "fail": []},
        "3": {"metrics": [], "ok": [], "fail": []},
    }
    all_group = {"metrics": [], "ok": [], "fail": []}

    try:
        for i, cf in enumerate(case_files, 1):
            case_name = os.path.splitext(cf)[0]
            case_path = os.path.join(CASE_DIR, cf)
            first_char = case_name[0] if case_name else ""
            tag = f"  [group {first_char}]" if first_char in "123" else ""
            print(f"\n[{i}/{len(case_files)}] CASE: {case_name}{tag}")

            try:
                section, metrics = run_single_case(case_path, case_name)
                individual_sections.append(section)
                all_group["metrics"].append(metrics)
                all_group["ok"].append(case_name)
                if first_char in "123":
                    groups[first_char]["metrics"].append(metrics)
                    groups[first_char]["ok"].append(case_name)
            except Exception as e:
                print(f"[!] Case {case_name} failed: {e}")
                individual_sections.append(
                    f"\n{'#' * 70}\n"
                    f"# CASE: {case_name}  [FAILED]\n"
                    f"{'#' * 70}\n\n"
                    f"[!] Exception: {e}\n"
                )
                all_group["fail"].append(case_name)
                if first_char in "123":
                    groups[first_char]["fail"].append(case_name)
                if original_main is not None:
                    with open(SRC_MAIN, "w") as f:
                        f.write(original_main)
    finally:
        if original_main is not None:
            with open(SRC_MAIN, "w") as f:
                f.write(original_main)
            print(f"\n[~] Original {SRC_MAIN} restored.")

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(INDIVIDUAL_LOG, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("=== INDIVIDUAL CASES REPORT (raw tool output + analysis) ===\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {ts}\n")
        f.write(f"Total cases: {len(case_files)}\n")
        f.write(f"Success: {len(all_group['ok'])}, "
                f"Failed: {len(all_group['fail'])}\n")
        f.write("\n".join(individual_sections))
        f.write("\n")

    with open(AGGREGATE_LOG, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("=== AGGREGATE REPORT ===\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {ts}\n\n")
        for prefix in ["1", "2", "3"]:
            g = groups[prefix]
            merged = merge_metrics(g["metrics"])
            f.write(format_aggregate(
                merged, f"CASES STARTING WITH '{prefix}'",
                g["ok"], g["fail"]
            ))
            f.write("\n\n")
        merged_all = merge_metrics(all_group["metrics"])
        f.write(format_aggregate(
            merged_all, "ALL CASES",
            all_group["ok"], all_group["fail"]
        ))
        f.write("\n")

    print("\n" + "=" * 60)
    print(f"[✓] Individual report : {INDIVIDUAL_LOG}")
    print(f"[✓] Aggregate report  : {AGGREGATE_LOG}")
    print(f"[✓] Success: {len(all_group['ok'])}, "
          f"Failed: {len(all_group['fail'])}")


if __name__ == "__main__":
    main()