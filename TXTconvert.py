import os
import sys
import time
from pathlib import Path
import argparse
from typing import List, Optional, Union, ClassVar

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

# 检查是否支持彩色输出
is_windows = sys.platform.startswith('win')
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

def install_opencc():
    """安装必要的依赖库"""
    try:
        import opencc
        return opencc
    except ImportError:
        print("正在安装opencc库...")
        try:
            from pip._internal import main as pip_main
            pip_main(['install', 'opencc-python-reimplemented'])
            import opencc
            print("opencc库安装成功!")
            return opencc
        except Exception as e:
            print(f"自动安装失败: {str(e)}")
            print("请手动执行: pip install opencc-python-reimplemented")
            sys.exit(1)

def convert_file(input_file: Union[str, Path], output_file: Union[str, Path], converter) -> bool:
    """
    转换单个文件
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        converter: OpenCC转换器实例
    
    Returns:
        bool: 转换是否成功
    """
    try:
        input_file = Path(input_file)
        output_file = Path(output_file)
        
        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 获取文件大小
        file_stat = input_file.stat()
        file_size = file_stat.st_size / (1024 * 1024)  # MB
        total_size = file_stat.st_size
        
        print(f"{Colors.OKBLUE}正在转换: {input_file} ({file_size:.2f} MB){Colors.ENDC}")
        
        start_time = time.time()
        
        # 根据文件大小动态调整批处理大小
        if total_size < 10 * 1024 * 1024:  # < 10MB
            batch_size = 1024 * 1024  # 1MB每批
        elif total_size < 100 * 1024 * 1024:  # < 100MB
            batch_size = 4 * 1024 * 1024  # 4MB每批
        else:  # >= 100MB
            batch_size = 8 * 1024 * 1024  # 8MB每批
        
        converted_chars = 0
        last_progress = -1
        
        with open(input_file, 'r', encoding='utf-8') as f_in:
            with open(output_file, 'w', encoding='utf-8') as f_out:
                while True:
                    chunk = f_in.read(batch_size)
                    if not chunk:
                        break
                    
                    # 转换当前批次
                    converted_chunk = converter.convert(chunk)
                    f_out.write(converted_chunk)
                    
                    converted_chars += len(chunk)
                    
                    # 显示进度（每1%更新一次，减少I/O操作）
                    progress = int((converted_chars / total_size) * 100)
                    if progress != last_progress:
                        print(f"\r{Colors.OKGREEN}进度: {progress:.1f}%{Colors.ENDC}", end='', flush=True)
                        last_progress = progress
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"\n{Colors.OKGREEN}转换完成! 耗时: {elapsed_time:.2f}秒{Colors.ENDC}")
        
        return True
        
    except FileNotFoundError:
        print(f"\n{Colors.FAIL}转换失败: 文件不存在 - {input_file}{Colors.ENDC}")
        return False
    except PermissionError:
        print(f"\n{Colors.FAIL}转换失败: 权限不足 - {input_file} 或 {output_file}{Colors.ENDC}")
        return False
    except UnicodeDecodeError:
        print(f"\n{Colors.FAIL}转换失败: 文件编码错误 - {input_file}{Colors.ENDC}")
        return False
    except Exception as e:
        print(f"\n{Colors.FAIL}转换失败: {str(e)}{Colors.ENDC}")
        return False

def batch_convert_traditional_to_simple(input_dir: Union[str, Path], output_dir: Optional[Union[str, Path]] = None, file_pattern: str = "*.txt") -> None:
    """
    批量转换繁体到简体
    
    Args:
        input_dir: 输入目录路径
        output_dir: 输出目录路径(默认为input_dir + "_converted")
        file_pattern: 文件匹配模式
    """
    # 安装和导入opencc
    opencc = install_opencc()
    converter = opencc.OpenCC('t2s.json')  # 繁体到简体
    
    # 处理路径
    input_path = Path(input_dir)
    
    if not input_path.exists() or not input_path.is_dir():
        print(f"{Colors.FAIL}错误: 目录不存在或不是有效目录 - {input_dir}{Colors.ENDC}")
        return
    
    if output_dir is None:
        output_path = input_path.parent / (input_path.name + "_converted")
    else:
        output_path = Path(output_dir)
    
    # 创建输出目录
    output_path.mkdir(exist_ok=True, parents=True)
    
    # 查找所有匹配的文件（去重）
    files = set()
    # 添加指定模式的文件
    files.update(input_path.glob(file_pattern))
    # 添加大写扩展名的文件
    if file_pattern.lower() == "*.txt":
        files.update(input_path.glob("*.TXT"))
    
    files = sorted(files)
    
    if not files:
        print(f"{Colors.WARNING}在目录 {input_dir} 中未找到 {file_pattern} 文件{Colors.ENDC}")
        return
    
    print(f"{Colors.OKBLUE}找到 {len(files)} 个文件待转换{Colors.ENDC}")
    print(f"{Colors.OKBLUE}输出目录: {output_path}{Colors.ENDC}")
    
    success_count = 0
    failed_files = []
    
    # 逐个转换文件
    for file_path in files:
        output_file = output_path / file_path.name
        
        if convert_file(file_path, output_file, converter):
            success_count += 1
        else:
            failed_files.append(file_path.name)
        
        print(f"{Colors.OKBLUE}-{Colors.ENDC}" * 50)
    
    # 输出汇总信息
    print(f"\n{Colors.HEADER}转换完成!{Colors.ENDC}")
    print(f"{Colors.OKGREEN}成功: {success_count}/{len(files)}{Colors.ENDC}")
    if failed_files:
        print(f"{Colors.FAIL}失败的文件: {', '.join(failed_files)}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}输出目录: {output_path}{Colors.ENDC}")

def convert_single_file(input_file: Union[str, Path], output_file: Optional[Union[str, Path]] = None) -> None:
    """
    转换单个文件
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径(默认为原文件名+simplified)
    """
    opencc = install_opencc()
    converter = opencc.OpenCC('t2s.json')
    
    input_path = Path(input_file)
    
    if not input_path.exists() or not input_path.is_file():
        print(f"{Colors.FAIL}错误: 文件不存在或不是有效文件 - {input_file}{Colors.ENDC}")
        return
    
    if output_file is None:
        output_path = input_path.parent / (input_path.stem + "_simplified" + input_path.suffix)
    else:
        output_path = Path(output_file)
    
    success = convert_file(input_path, output_path, converter)
    
    if success:
        print(f"{Colors.OKBLUE}输出文件: {output_path}{Colors.ENDC}")

def main() -> None:
    """
    主函数，处理命令行参数
    """
    parser = argparse.ArgumentParser(description='批量繁体转简体转换工具')
    parser.add_argument('--input', '-i', required=True, help='输入文件或目录路径')
    parser.add_argument('--output', '-o', help='输出文件或目录路径')
    parser.add_argument('--pattern', '-p', default='*.txt', help='文件匹配模式(默认为*.txt)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        # 单个文件转换
        convert_single_file(args.input, args.output)
    elif input_path.is_dir():
        # 批量转换
        batch_convert_traditional_to_simple(
            args.input, 
            args.output, 
            args.pattern
        )
    else:
        print(f"{Colors.FAIL}错误: 输入路径不存在或不是有效文件/目录 - {args.input}{Colors.ENDC}")

if __name__ == "__main__":
    # 如果直接运行，显示使用说明
    if len(sys.argv) == 1:
        print(f"{Colors.HEADER}繁体转简体批量转换工具{Colors.ENDC}")
        print(f"{Colors.HEADER}={Colors.ENDC}" * 50)
        
        # 交互式输入
        input_path = input(f"{Colors.OKBLUE}请输入文件或目录路径: {Colors.ENDC}").strip().strip('"')
        
        if not input_path:
            print(f"{Colors.OKBLUE}使用示例:{Colors.ENDC}")
            print(f"  {Colors.OKGREEN}单个文件: python TXTconvert.py --input input.txt --output output.txt{Colors.ENDC}")
            print(f"  {Colors.OKGREEN}批量转换: python TXTconvert.py --input ./documents --output ./converted{Colors.ENDC}")
            print(f"  {Colors.OKGREEN}带文件模式: python TXTconvert.py --input ./docs --pattern \"*.txt\"{Colors.ENDC}")
            sys.exit(0)
        
        input_path_obj = Path(input_path)
        
        if input_path_obj.is_file():
            output_file = input(f"{Colors.OKBLUE}输出文件路径(直接回车使用默认名称): {Colors.ENDC}").strip()
            convert_single_file(input_path, output_file if output_file else None)
        elif input_path_obj.is_dir():
            output_dir = input(f"{Colors.OKBLUE}输出目录路径(直接回车使用默认目录): {Colors.ENDC}").strip()
            pattern = input(f"{Colors.OKBLUE}文件匹配模式(直接回车使用*.txt): {Colors.ENDC}").strip() or "*.txt"
            batch_convert_traditional_to_simple(input_path, output_dir if output_dir else None, pattern)
        else:
            print(f"{Colors.FAIL}错误: 输入路径不存在或不是有效文件/目录 - {input_path}{Colors.ENDC}")
    else:
        main()