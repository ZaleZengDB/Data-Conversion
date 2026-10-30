import os
import collections
import time
from typing import List, Dict, Tuple, Set, Optional, NamedTuple, ClassVar

# 彩色输出支持
class Colors:
    HEADER: ClassVar[str] = '\033[95m'
    OKBLUE: ClassVar[str] = '\033[94m'
    OKGREEN: ClassVar[str] = '\033[92m'
    WARNING: ClassVar[str] = '\033[93m'
    FAIL: ClassVar[str] = '\033[91m'
    ENDC: ClassVar[str] = '\033[0m'
    BOLD: ClassVar[str] = '\033[1m'
    UNDERLINE: ClassVar[str] = '\033[4m'


def separator(char: str = '=', length: int = 80) -> str:
    """生成分隔线字符串"""
    return char * length


# 检查是否支持彩色输出
is_windows = os.name == 'nt'
if is_windows:
    # Windows终端不支持ANSI转义序列，使用空字符串
    Colors.HEADER = ''
    Colors.OKBLUE = ''
    Colors.OKGREEN = ''
    Colors.WARNING = ''
    Colors.FAIL = ''
    Colors.ENDC = ''
    Colors.BOLD = ''
    Colors.UNDERLINE = ''

class FileInfo(NamedTuple):
    """文件信息命名元组"""
    name_without_ext: str
    original_name: str
    full_path: str


def collect_file_info(folder_path: str) -> List[FileInfo]:
    """
    收集文件夹中的所有文件信息
    
    Args:
        folder_path: 文件夹路径
    
    Returns:
        文件信息列表
    """
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return []
    
    file_info = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            name_without_ext = os.path.splitext(file)[0]
            file_info.append(FileInfo(
                name_without_ext=name_without_ext,
                original_name=file,
                full_path=os.path.join(root, file)
            ))
    return file_info

def find_exact_duplicates(folder_path: str) -> Dict[str, List[str]]:
    """
    查找完全重复的文件名
    """
    file_info_list = collect_file_info(folder_path)
    
    file_dict = {}
    for info in file_info_list:
        if info.original_name not in file_dict:
            file_dict[info.original_name] = []
        file_dict[info.original_name].append(info.full_path)

    return {name: paths for name, paths in file_dict.items() if len(paths) > 1}

def find_prefix_duplicates(folder_path: str, min_prefix_length: int = 3) -> List[Tuple[str, List[str], List[str], str]]:
    """
    查找前缀重复的文件名

    Args:
        folder_path: 要检查的文件夹路径
        min_prefix_length: 最小前缀长度，默认3个字符

    Returns:
        包含前缀、文件列表、路径列表和关系描述的元组列表
    """
    file_info_list = collect_file_info(folder_path)
    
    # 按文件名排序，这样相似的文件名会相邻
    file_info_list.sort(key=lambda x: x.name_without_ext)

    # 使用字典记录每个前缀对应的文件
    prefix_map = collections.defaultdict(list)

    # 为每个文件名生成所有可能的前缀
    for info in file_info_list:
        # 生成长度从min_prefix_length到文件名长度的所有前缀
        for length in range(min_prefix_length, len(info.name_without_ext) + 1):
            prefix = info.name_without_ext[:length]
            prefix_map[prefix].append((info.original_name, info.full_path))

    # 找出有多个文件共享的前缀
    duplicate_prefixes = {prefix: files for prefix, files in prefix_map.items() if len(files) > 1}

    # 组织结果，避免重复报告
    results = []
    processed_files = set()

    # 按前缀长度降序遍历，优先处理更长（更具体）的前缀，避免短前缀提前标记文件导致漏报
    for prefix, files in sorted(duplicate_prefixes.items(), key=lambda x: len(x[0]), reverse=True):
        # 跳过已经被处理过的文件
        current_files = [(name, path) for name, path in files if path not in processed_files]
        if len(current_files) < 2:
            continue

        # 找出这个前缀组中最短的文件名作为基础
        base_files = sorted(current_files, key=lambda x: len(x[0]))
        base_name = base_files[0][0]

        # 找出所有以这个基础文件名为前缀的文件
        related_files = [(name, path) for name, path in current_files if name.startswith(base_name) or base_name.startswith(name)]

        if len(related_files) > 1:
            # 提取所有文件名
            filenames = [name for name, path in related_files]
            paths = [path for name, path in related_files]

            # 生成关系描述
            shortest = min(filenames, key=len)
            longest = max(filenames, key=len)
            relationship = f"'{shortest}' 是 '{longest}' 的前缀" if shortest != longest else "完全重复"

            results.append((prefix, filenames, paths, relationship))

            # 标记这些文件为已处理
            for _, path in related_files:
                processed_files.add(path)

    # 按前缀长度排序，较长的前缀排在前面
    results.sort(key=lambda x: len(x[0]), reverse=True)

    return results

def find_direct_prefix_pairs(folder_path: str, min_prefix_length: int = 3) -> List[Tuple[str, str, str, str, str]]:
    """
    直接查找前缀-扩展文件对

    Args:
        folder_path: 要检查的文件夹路径
        min_prefix_length: 最小前缀长度

    Returns:
        包含基础文件名、扩展文件名、基础文件路径、扩展文件路径和关系描述的元组列表
    """
    file_info_list = collect_file_info(folder_path)
    
    # 构建字典：不含扩展名的文件名 -> 文件信息列表（同名不同扩展名都会保留，避免覆盖）
    name_to_infos: Dict[str, List[FileInfo]] = {}
    for info in file_info_list:
        name_to_infos.setdefault(info.name_without_ext, []).append(info)

    # 获取所有不含扩展名的文件名并按长度排序
    names = sorted(name_to_infos.keys(), key=len)

    results = []
    processed = set()

    # 检查每个文件名是否是其他文件名的前缀
    for i, name1 in enumerate(names):
        if name1 in processed:
            continue

        # 找出所有以name1为前缀的较长文件名
        extensions = []
        for name2 in names[i+1:]:
            if name2.startswith(name1) and len(name2) > len(name1) and len(name1) >= min_prefix_length:
                extensions.append(name2)

        if extensions:
            # 对每个基础文件与每个扩展文件，记录配对信息
            for base_info in name_to_infos[name1]:
                for ext_name in extensions:
                    for ext_info in name_to_infos[ext_name]:
                        # 计算额外的字符
                        extra_chars = ext_name[len(name1):]
                        relationship = f"'{name1}' + '{extra_chars}' = '{ext_name}'"

                        results.append((
                            base_info.original_name,   # 基础文件名
                            ext_info.original_name,    # 扩展文件名
                            base_info.full_path,       # 基础文件路径
                            ext_info.full_path,        # 扩展文件路径
                            relationship
                        ))

            processed.add(name1)
            for ext_name in extensions:
                processed.add(ext_name)

    return results

def print_exact_duplicates(duplicates: Dict[str, List[str]], folder_path: str):
    """打印完全重复的文件名"""
    if not duplicates:
        print(f"{Colors.OKGREEN}在文件夹 '{folder_path}' 中未发现完全重复的文件名{Colors.ENDC}")
        return

    print(f"\n{Colors.OKBLUE}🔍 在文件夹 '{folder_path}' 中发现 {len(duplicates)} 个完全重复的文件名：{Colors.ENDC}")
    print(f"{Colors.HEADER}{separator('=', 80)}{Colors.ENDC}")

    for i, (filename, paths) in enumerate(duplicates.items(), 1):
        print(f"{Colors.OKBLUE}{i}. 文件名: {filename}{Colors.ENDC}")
        print(f"   {Colors.WARNING}重复次数: {len(paths)} 次{Colors.ENDC}")
        print(f"   {Colors.OKBLUE}具体路径:{Colors.ENDC}")
        for path in paths:
            print(f"     📁 {path}")
        print(f"   {Colors.OKBLUE}{'─' * 60}{Colors.ENDC}")

def print_prefix_duplicates(prefix_results: List[Tuple[str, List[str], List[str], str]], folder_path: str):
    """打印前缀重复的文件名"""
    if not prefix_results:
        print(f"{Colors.OKGREEN}在文件夹 '{folder_path}' 中未发现前缀重复的文件名{Colors.ENDC}")
        return

    print(f"\n{Colors.OKBLUE}🎯 在文件夹 '{folder_path}' 中发现 {len(prefix_results)} 组前缀重复的文件名：{Colors.ENDC}")
    print(f"{Colors.HEADER}{separator('=', 80)}{Colors.ENDC}")

    for i, (prefix, filenames, paths, relationship) in enumerate(prefix_results, 1):
        print(f"{Colors.OKBLUE}{i}. 共同前缀: '{prefix}'{Colors.ENDC}")
        print(f"   {Colors.WARNING}关系: {relationship}{Colors.ENDC}")
        print(f"   {Colors.OKBLUE}涉及文件: {', '.join(filenames)}{Colors.ENDC}")
        print(f"   {Colors.OKBLUE}具体路径:{Colors.ENDC}")
        for path in paths:
            print(f"     📁 {path}")
        print(f"   {Colors.OKBLUE}{'─' * 60}{Colors.ENDC}")

def print_direct_prefix_pairs(pair_results: List[Tuple[str, str, str, str, str]], folder_path: str):
    """直接打印前缀文件对"""
    if not pair_results:
        print(f"{Colors.OKGREEN}在文件夹 '{folder_path}' 中未发现前缀文件对{Colors.ENDC}")
        return

    print(f"\n{Colors.OKBLUE}🎯 在文件夹 '{folder_path}' 中发现 {len(pair_results)} 个前缀文件对：{Colors.ENDC}")
    print(f"{Colors.HEADER}{separator('=', 80)}{Colors.ENDC}")

    for i, (base_name, ext_name, base_path, ext_path, relationship) in enumerate(pair_results, 1):
        print(f"{Colors.OKBLUE}{i}. {relationship}{Colors.ENDC}")
        print(f"   {Colors.WARNING}基础文件: {base_name}{Colors.ENDC}")
        print(f"     路径: {base_path}")
        print(f"   {Colors.WARNING}扩展文件: {ext_name}{Colors.ENDC}")
        print(f"     路径: {ext_path}")
        print(f"   {Colors.OKBLUE}{'─' * 60}{Colors.ENDC}")

def analyze_prefix_patterns(prefix_results: List[Tuple[str, List[str], List[str], str]]) -> Dict[str, int]:
    """
    分析前缀重复模式
    
    Args:
        prefix_results: 前缀重复检测结果
    
    Returns:
        扩展模式统计
    """
    patterns = {
        "括号扩展": 0,      # 如：文件名 -> 文件名(部分)
        "数字扩展": 0,      # 如：文件 -> 文件1, 文件2
        "文字扩展": 0,      # 如：文档 -> 文档副本, 文档最终版
        "其他扩展": 0
    }

    for prefix, filenames, paths, relationship in prefix_results:
        # 找出最短和最长文件名
        if len(filenames) < 2:
            continue

        shortest = min(filenames, key=len)
        longest = max(filenames, key=len)

        # 计算扩展部分
        extension = longest[len(shortest):]

        # 分类扩展模式
        if extension.startswith('(') and extension.endswith(')'):
            patterns["括号扩展"] += 1
        elif extension.isdigit() or (extension and all(c.isdigit() for c in extension.strip())):
            patterns["数字扩展"] += 1
        elif any(keyword in extension for keyword in ['副本', '复制', 'copy', '部分', '节选', '最终', '修改']):
            patterns["文字扩展"] += 1
        else:
            patterns["其他扩展"] += 1

    return patterns

def main():
    """
    主函数：获取用户输入并执行重复文件检测
    """
    print(f"{Colors.HEADER}📁 智能文件名前缀重复检测工具{Colors.ENDC}")
    print(f"{Colors.HEADER}{separator('=', 50)}{Colors.ENDC}")

    # 获取文件夹路径
    folder_path = input(f"{Colors.OKBLUE}请输入要检查的文件夹路径: {Colors.ENDC}").strip().strip('"\'')

    if not os.path.exists(folder_path):
        print(f"{Colors.FAIL}❌ 错误：路径 '{folder_path}' 不存在{Colors.ENDC}")
        return

    if not os.path.isdir(folder_path):
        print(f"{Colors.FAIL}❌ 错误：'{folder_path}' 不是一个文件夹{Colors.ENDC}")
        return

    print(f"\n{Colors.OKBLUE}🎛️  选择检测模式:{Colors.ENDC}")
    print(f"{Colors.OKGREEN}1. 完全重复检测（文件名完全相同）{Colors.ENDC}")
    print(f"{Colors.OKGREEN}2. 前缀重复检测（文件名是其他文件名的前缀）{Colors.ENDC}")
    print(f"{Colors.OKGREEN}3. 直接前缀对检测（显示具体的前缀-扩展文件对）{Colors.ENDC}")
    print(f"{Colors.OKGREEN}4. 全面检测（所有模式）{Colors.ENDC}")

    choice = input(f"{Colors.OKBLUE}请选择模式 (1-4): {Colors.ENDC}").strip()

    # 获取最小前缀长度
    min_prefix_length = 3
    if choice in ["2", "3", "4"]:
        try:
            length_input = input(f"{Colors.OKBLUE}请输入最小前缀长度 (默认3): {Colors.ENDC}").strip()
            if length_input:
                min_prefix_length = int(length_input)
                if min_prefix_length < 1:
                    print(f"{Colors.WARNING}⚠️  最小前缀长度至少为1，使用默认值3{Colors.ENDC}")
                    min_prefix_length = 3
        except ValueError:
            print(f"{Colors.WARNING}⚠️  输入无效，使用默认最小前缀长度3{Colors.ENDC}")

    print(f"\n{Colors.OKBLUE}🔍 开始检测，最小前缀长度: {min_prefix_length}{Colors.ENDC}")
    print(f"{Colors.WARNING}⏳ 请稍候...{Colors.ENDC}")

    start_time = time.time()
    results = {}

    if choice == "1" or choice == "4":
        # 完全重复检测
        print(f"{Colors.OKBLUE}正在检测完全重复的文件名...{Colors.ENDC}")
        exact_duplicates = find_exact_duplicates(folder_path)
        results["exact"] = exact_duplicates

    if choice == "2" or choice == "4":
        # 前缀重复检测
        print(f"{Colors.OKBLUE}正在检测前缀重复的文件名...{Colors.ENDC}")
        prefix_duplicates = find_prefix_duplicates(folder_path, min_prefix_length)
        results["prefix"] = prefix_duplicates

    if choice == "3" or choice == "4":
        # 直接前缀对检测
        print(f"{Colors.OKBLUE}正在检测前缀文件对...{Colors.ENDC}")
        prefix_pairs = find_direct_prefix_pairs(folder_path, min_prefix_length)
        results["pairs"] = prefix_pairs

    elapsed_time = time.time() - start_time

    # 输出结果
    print(f"\n{Colors.HEADER}{separator('=', 80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}📊 检测结果汇总{Colors.ENDC}")
    print(f"{Colors.HEADER}{separator('=', 80)}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}检测耗时: {elapsed_time:.2f} 秒{Colors.ENDC}")

    if "exact" in results:
        print_exact_duplicates(results["exact"], folder_path)

    if "prefix" in results:
        print_prefix_duplicates(results["prefix"], folder_path)

        # 分析前缀模式
        if results["prefix"]:
            patterns = analyze_prefix_patterns(results["prefix"])
            print(f"\n{Colors.OKBLUE}📈 前缀重复模式分析:{Colors.ENDC}")
            for pattern, count in patterns.items():
                if count > 0:
                    print(f"   {Colors.WARNING}{pattern}: {count} 组{Colors.ENDC}")

    if "pairs" in results:
        print_direct_prefix_pairs(results["pairs"], folder_path)

    # 统计信息
    total_groups = 0
    if "exact" in results:
        total_groups += len(results["exact"])
    if "prefix" in results:
        total_groups += len(results["prefix"])
    if "pairs" in results:
        total_groups += len(results["pairs"])

    if total_groups > 0:
        print(f"\n{Colors.WARNING}💡 建议: 发现 {total_groups} 组重复或前缀重复文件，建议进行整理以避免混淆{Colors.ENDC}")
    else:
        print(f"\n{Colors.OKGREEN}✅ 恭喜！在 '{folder_path}' 中未发现重复或前缀重复的文件名{Colors.ENDC}")
    
    print(f"\n{Colors.HEADER}{separator('=', 50)}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}检测完成！{Colors.ENDC}")

if __name__ == "__main__":
    main()