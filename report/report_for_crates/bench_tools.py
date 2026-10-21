import subprocess
import os
import re
import glob
from datetime import datetime

# ============ 配置 ============
SRC_DIR    = "src"
CARGO_TOML = "Cargo.toml"
LOG_FILE   = "combined_test_report.log"

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


# ============ safedrop 命令构建 ============
def _read_edition():
    try:
        with open(CARGO_TOML, "r") as f:
            text = f.read()
        m = re.search(r'^\s*edition\s*=\s*"(\d{4})"', text, re.MULTILINE)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "2021"


def build_safedrop_cmd():
    """根据 crate 类型选择 safedrop 命令。

    - lib crate（有 src/lib.rs）→ rustc +safedrop --crate-type lib
      （不链接、不需要 main / panic_handler，编译产物丢弃到 /tmp）
    - bin crate（只有 src/main.rs）→ rustc +safedrop src/main.rs
    """
    lib_path  = os.path.join(SRC_DIR, "lib.rs")
    main_path = os.path.join(SRC_DIR, "main.rs")
    if os.path.exists(lib_path):
        edition = _read_edition()
        return (f"rustc +safedrop --crate-type lib --edition {edition} "
                f"{lib_path} -o /tmp/safedrop_out.rlib")
    if os.path.exists(main_path):
        return f"rustc +safedrop {main_path}"
    return None


# ============ RAPX warning 合并（含 Dangling Pointer） ============
def parse_rapx_warnings(text):
    cleaned = CSI_RE.sub("", text)
    blocks = re.split(
        r"(?=^warning:\s*(?:double\s*free|use[- ]?after[- ]?free|dangling\s*pointer))",
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
        elif re.search(r"dangling\s*pointer", title, re.IGNORECASE):
            wtype = "Dangling Pointer"
        else:
            continue

        loc = re.search(r"-->\s*(\S+):(\d+):(\d+)", block)
        if not loc:
            continue
        file, line, _col = loc.groups()

        key = (wtype, file, line)
        if key not in merged:
            merged[key] = {"type": wtype, "file": file, "line": line,
                           "confidences": set(), "mir_details": []}

        for c in re.findall(
            r"(?:double\s*free|use[- ]?after[- ]?free|dangling\s*pointer)"
            r"\s*\(confidence\s*(\d+)%\)",
            block, re.IGNORECASE
        ):
            merged[key]["confidences"].add(int(c))

        for d in re.findall(r"MIR detail:\s*(.*)", block):
            d = d.strip()
            if d and d not in merged[key]["mir_details"]:
                merged[key]["mir_details"].append(d)

    result = []
    for v in merged.values():
        result.append({
            "type": v["type"], "file": v["file"], "line": v["line"],
            "confidences": sorted(v["confidences"], reverse=True),
            "mir_details": v["mir_details"],
        })
    result.sort(key=lambda x: (x["type"], x["file"], int(x["line"])))
    return result


# ============ SAFEDROP 计数（含 Dangling Pointer） ============
def parse_safedrop_counts(text):
    cleaned = CSI_RE.sub("", text)
    out = {}
    specs = [
        ("Double Free", [r"Double Free Bugs Exist:"]),
        ("Use After Free", [r"Use After Free Bugs Exist:"]),
        ("Dangling Pointer", [r"Dangling Pointer Bugs Exist:",
                              r"Dangling Pointers? Exist:"]),
    ]
    for label, patterns in specs:
        count, found = 0, False
        for pat in patterns:
            m = re.search(rf"{pat}\n(.*?)(?=\n\n|\n[A-Z]|$)",
                          cleaned, re.DOTALL)
            if m:
                found = True
                count = len(re.findall(r"occurs in", m.group(1)))
                break
        if not found and label == "Dangling Pointer":
            count = len(re.findall(r"[Dd]angling [Pp]ointer", cleaned))
        out[label] = count
    return out


# ============ 执行 ============
def run_experiment():
    with open(LOG_FILE, "w") as f:
        f.write(f"=== EXPERIMENT LOG: {datetime.now()} ===\n\n")

    safedrop_cmd = build_safedrop_cmd()
    tools = [
        ("rapx", "cargo +nightly-2025-12-06 rapx check -f"),
        ("safedrop", safedrop_cmd),
        ("charon_rudra", None),  # 两步，动态处理
    ]

    for name, cmd in tools:
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        if name == "safedrop":
            if cmd is None:
                print(f"[!] safedrop: no src/lib.rs or src/main.rs, skipping.")
                continue
            print(f"[*] Executing safedrop...")
            print(f"    [~] cmd: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                    text=True, env=env)
            with open(LOG_FILE, "a") as f:
                f.write(f"[[TOOL_START: {name}]]\n")
                f.write(f"STDOUT:\n{result.stdout}\n")
                f.write(f"STDERR:\n{result.stderr}\n")
                f.write(f"[[TOOL_END: {name}]]\n\n")
            subprocess.run("cargo clean", shell=True, capture_output=True)
            continue

        if name == "charon_rudra":
            print(f"[*] Executing charon_rudra...")
            before = set(glob.glob("*.ullbc"))
            r1 = subprocess.run("charon --ullbc", shell=True,
                                capture_output=True, text=True, env=env)
            after = set(glob.glob("*.ullbc"))
            new_ullbc = list(after - before)
            if not new_ullbc and after:
                new_ullbc = [max(after, key=os.path.getmtime)]

            if not new_ullbc:
                print("[!] charon did not produce any .ullbc file")
                with open(LOG_FILE, "a") as f:
                    f.write(f"[[TOOL_START: {name}]]\n")
                    f.write(f"STDOUT:\n{r1.stdout}\n")
                    f.write(f"STDERR:\n{r1.stderr}\n")
                    f.write("[!] No .ullbc produced by `charon --ullbc`\n")
                    f.write(f"[[TOOL_END: {name}]]\n\n")
                subprocess.run("cargo clean", shell=True, capture_output=True)
                continue

            ullbc_file = new_ullbc[0]
            print(f"    [~] charon produced {ullbc_file}, "
                  f"passing to cargo-charon-rudra")
            r2 = subprocess.run(
                f"cargo-charon-rudra --file {ullbc_file}",
                shell=True, capture_output=True, text=True, env=env
            )
            with open(LOG_FILE, "a") as f:
                f.write(f"[[TOOL_START: {name}]]\n")
                f.write(f"STDOUT:\n{r1.stdout}\n{r2.stdout}\n")
                f.write(f"STDERR:\n{r1.stderr}\n{r2.stderr}\n")
                f.write(f"[[TOOL_END: {name}]]\n\n")
            try:
                os.remove(ullbc_file)
            except OSError:
                pass
            subprocess.run("cargo clean", shell=True, capture_output=True)
            continue

        # rapx 单命令
        print(f"[*] Executing {name}...")
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, env=env)
        with open(LOG_FILE, "a") as f:
            f.write(f"[[TOOL_START: {name}]]\n")
            f.write(f"STDOUT:\n{result.stdout}\n")
            f.write(f"STDERR:\n{result.stderr}\n")
            f.write(f"[[TOOL_END: {name}]]\n\n")
        subprocess.run("cargo clean", shell=True, capture_output=True)


# ============ 分析 ============
def analyze_log():
    with open(LOG_FILE, "r") as f:
        content = f.read()

    summary = ["\n" + "=" * 60,
               "### INDIVIDUAL TOOL ANALYSIS REPORT ###",
               "=" * 60 + "\n"]

    for name in ["rapx", "safedrop", "charon_rudra"]:
        pattern = rf"\[\[TOOL_START: {name}\]\].*?\[\[TOOL_END: {name}\]\]"
        tool_block = re.search(pattern, content, re.DOTALL)
        if not tool_block:
            continue
        block_text = tool_block.group(0)
        tool_report = [f"[{name.upper()}]:"]

        if name == "rapx":
            items = parse_rapx_warnings(block_text)
            counts = {"Double Free": 0, "Use-After-Free": 0, "Dangling Pointer": 0}
            for it in items:
                counts[it["type"]] = counts.get(it["type"], 0) + 1
            tool_report.append(f"  - Double Free (unique locations): {counts['Double Free']}")
            tool_report.append(f"  - Use-After-Free (unique locations): {counts['Use-After-Free']}")
            tool_report.append(f"  - Dangling Pointer (unique locations): {counts['Dangling Pointer']}")
            if items:
                tool_report.append("  - Detailed issues (merged by location):")
                for it in items:
                    conf = ", ".join(f"{c}%" for c in it["confidences"]) or "N/A"
                    tool_report.append(
                        f"    * {it['type']} (confidence {conf}) "
                        f"at {it['file']}:{it['line']}"
                    )
                    for d in it["mir_details"]:
                        tool_report.append(f"      - MIR detail: {d}")
            else:
                tool_report.append("  - Detailed issues: (none)")

        elif name == "safedrop":
            c = parse_safedrop_counts(block_text)
            tool_report.append(f"  - Double Free (occurs lines): {c['Double Free']}")
            tool_report.append(f"  - Use After Free (occurs lines): {c['Use After Free']}")
            tool_report.append(f"  - Dangling Pointer (count): {c['Dangling Pointer']}")

        elif name == "charon_rudra":
            color_counts = {}
            for params in SGR_RE.findall(block_text):
                for tok in params.split(";"):
                    cname = COLOR_CODE_MAP.get(tok)
                    if cname:
                        color_counts[cname] = color_counts.get(cname, 0) + 1
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
            if highlighted:
                tool_report.append(
                    f"  - Highlighted Statements ({len(highlighted)} unique):")
                for tag, text in highlighted:
                    tool_report.append(f"    * [{tag}] {text}")
            else:
                tool_report.append("  - Highlighted Statements: (none)")

        summary.append("\n".join(tool_report))

    final_str = "\n".join(summary)
    print(final_str)
    with open(LOG_FILE, "a") as f:
        f.write("\n" + final_str)


if __name__ == "__main__":
    run_experiment()
    analyze_log()