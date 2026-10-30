import os
import time
import traceback
import pandas as pd
from scipy.io import savemat
import re
import numpy as np
from datetime import datetime


def ensure_directory(directory):
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def validate_input_path(path):
    """验证输入路径是否存在且为目录"""
    if not isinstance(path, str):
        raise TypeError("路径必须是字符串")
    if not os.path.isdir(path):
        raise ValueError(f"指定的路径不存在或不是目录: {path}")


def format_time(seconds):
    """格式化时间为可读字符串"""
    return f"{seconds:.2f} 秒"

# 参考路径 C:/Users/Administrator/Desktop/data/EFT test/0415/2号机/testdata
# 参考路径 C:/Users/Administrator/Desktop/data/Standard EMG/Record
def txt_to_excel(folder_path, output_dir=None, overwrite=True, batch_size=1000, verbose=True):
    """将指定文件夹内的txt文件转换为数值格式的Excel文件
    
    参数:
        folder_path: str - 包含txt文件的文件夹路径
        output_dir: str - 输出Excel文件的目录，默认为与txt文件相同目录
        overwrite: bool - 是否覆盖已存在的Excel文件，默认为True
        batch_size: int - 批处理大小，用于处理大文件，默认为1000行
        verbose: bool - 是否显示详细日志，默认为True
    
    返回:
        dict - 包含处理结果的字典，包括：
            - processed_files: 成功处理的文件数
            - error_files: 错误文件数
            - success_list: 成功处理的文件列表
            - error_list: 错误文件列表
            - details: 详细处理信息
            - total_time: 总处理时间
    """
    # 输入验证
    validate_input_path(folder_path)
    
    if output_dir is not None and not isinstance(output_dir, str):
        raise TypeError("output_dir 必须是字符串")
    
    if not isinstance(overwrite, bool):
        raise TypeError("overwrite 必须是布尔值")
    
    if not isinstance(batch_size, int):
        raise TypeError("batch_size 必须是整数")
    
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于0")
    
    if not isinstance(verbose, bool):
        raise TypeError("verbose 必须是布尔值")
    
    processed_files = 0
    error_files = 0
    success_list = []
    error_list = []
    details = {}
    
    # 支持的分隔符列表 - 用于解析txt文件中的数据
    delimiters = ['/', ' ', '\t', ',', ';', '|']
    # 尝试的编码列表 - 用于处理不同编码的txt文件
    encodings = ['utf-8', 'gbk', 'gb2312', 'ansi', 'latin-1']
    
    # 如果未指定输出目录，使用输入目录
    if output_dir is None:
        output_dir = folder_path
    else:
        # 确保输出目录存在
        ensure_directory(output_dir)
    
    if verbose:
        print(f"开始处理文件夹: {folder_path}")
        print(f"输出目录: {output_dir}")
        print(f"是否覆盖现有文件: {overwrite}")
        print()
    
    start_time = time.time()
    
    for filename in os.listdir(folder_path):
        if filename.endswith('.txt'):
            txt_path = os.path.join(folder_path, filename)
            file_details = {
                'input_file': filename,
                'encoding': None,
                'lines_processed': 0,
                'status': 'pending'
            }
            
            # 读取并解析txt文件
            data = []
            error_occurred = False
            encoding_used = None
            
            # 尝试不同的编码 - 自动检测文件编码
            for encoding in encodings:
                try:
                    with open(txt_path, 'r', encoding=encoding) as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if line:
                                try:
                                    # 尝试使用多种分隔符解析 - 自动检测数据分隔符
                                    parsed = False
                                    for delimiter in delimiters:
                                        if delimiter in line:
                                            # 分割并过滤空值，然后转换为浮点数
                                            row = [float(x.strip()) for x in line.split(delimiter) if x.strip()]
                                            data.append(row)
                                            parsed = True
                                            break
                                    
                                    # 如果没有找到分隔符，尝试将整个行作为单个数值
                                    if not parsed:
                                        row = [float(line.strip())]
                                        data.append(row)
                                except ValueError:
                                    if verbose:
                                        print(f"错误：文件 {filename} 第 {line_num} 行包含非数值数据: {line}")
                                    error_occurred = True
                                    break  # 遇到错误时跳过当前文件
                    
                    if not error_occurred:
                        encoding_used = encoding
                        file_details['encoding'] = encoding
                        file_details['lines_processed'] = len(data)
                        break
                except UnicodeDecodeError:
                    continue  # 尝试下一种编码
            
            if not encoding_used:
                if verbose:
                    print(f"错误：无法使用任何支持的编码读取文件 {filename}")
                error_files += 1
                error_list.append(filename)
                file_details['status'] = 'encoding_error'
                details[filename] = file_details
                continue

            # 创建DataFrame并保存为Excel
            if data and not error_occurred:
                # 对于大文件，使用批处理
                if len(data) > batch_size and verbose:
                    print(f"处理大文件: {filename} (共 {len(data)} 行)")
                
                df = pd.DataFrame(data)
                excel_filename = os.path.splitext(filename)[0] + '.xlsx'
                excel_path = os.path.join(output_dir, excel_filename)
                
                # 检查是否覆盖
                if os.path.exists(excel_path):
                    if overwrite:
                        if verbose:
                            print(f"覆盖: 文件 {excel_filename} 已存在，正在覆盖")
                    else:
                        if verbose:
                            print(f"跳过: 文件 {excel_filename} 已存在 (使用 overwrite=True 覆盖)")
                        error_files += 1
                        error_list.append(filename)
                        file_details['status'] = 'file_exists'
                        details[filename] = file_details
                        continue
                
                # 优化Excel写入
                try:
                    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, header=False)
                    
                    if verbose:
                        print(f'转换完成: {filename} -> {excel_filename} (数值格式)')
                    processed_files += 1
                    success_list.append(filename)
                    file_details['status'] = 'success'
                    file_details['output_file'] = excel_filename
                except Exception as e:
                    if verbose:
                        print(f"错误：保存文件 {excel_filename} 时出错: {e}")
                    error_files += 1
                    error_list.append(filename)
                    file_details['status'] = 'save_error'
                    file_details['error_message'] = str(e)
            elif error_occurred:
                error_files += 1
                error_list.append(filename)
                file_details['status'] = 'parse_error'
            
            details[filename] = file_details
    
    end_time = time.time()
    total_time = end_time - start_time
    
    if verbose:
        print(f"\n转换完成！")
        print(f"总耗时: {total_time:.2f} 秒")
        print(f"成功处理: {processed_files} 个文件")
        print(f"错误文件: {error_files} 个文件")
    
    return {
        'processed_files': processed_files,
        'error_files': error_files,
        'success_list': success_list,
        'error_list': error_list,
        'details': details,
        'total_time': total_time
    }

def excel_to_mat(folder_path, output_dir=None, mat_filename='EMGStandardData.mat', scale_factor=1e6, scale_original=False, batch_size=1000, verbose=True, var_name_prefix='EMGBuffer_1000_Test', var_name_suffix='4ch'):
    """将Excel文件转换为转置后的MATLAB .mat文件
    
    参数:
        folder_path: str - 包含Excel文件的文件夹路径
        output_dir: str - 输出MAT文件的目录，默认为与Excel文件相同目录
        mat_filename: str - 输出MAT文件的名称，默认为'EMGStandardData.mat'
        scale_factor: float - 数据缩放因子，默认为1e6
        scale_original: bool - 是否缩放原始数据文件，默认为False
        batch_size: int - 批处理大小，用于处理大文件，默认为1000行
        verbose: bool - 是否显示详细日志，默认为True
        var_name_prefix: str - 变量名前缀，默认为'EMGBuffer_1000_Test'
        var_name_suffix: str - 变量名后缀，默认为'4ch'
    
    返回:
        dict - 包含处理结果的字典，包括：
            - processed_files: 成功处理的文件数
            - error_files: 错误文件数
            - success_list: 成功处理的文件列表
            - error_list: 错误文件列表
            - details: 详细处理信息
            - total_time: 总处理时间
    """
    
    # 输入验证
    validate_input_path(folder_path)
    
    if output_dir is not None and not isinstance(output_dir, str):
        raise TypeError("output_dir 必须是字符串")
    
    if not isinstance(mat_filename, str):
        raise TypeError("mat_filename 必须是字符串")
    
    if not isinstance(scale_factor, (int, float)):
        raise TypeError("scale_factor 必须是数字")
    
    if scale_factor <= 0:
        raise ValueError("scale_factor 必须大于0")
    
    if not isinstance(scale_original, bool):
        raise TypeError("scale_original 必须是布尔值")
    
    if not isinstance(batch_size, int):
        raise TypeError("batch_size 必须是整数")
    
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于0")
    
    if not isinstance(verbose, bool):
        raise TypeError("verbose 必须是布尔值")
    
    if not isinstance(var_name_prefix, str):
        raise TypeError("var_name_prefix 必须是字符串")
    
    if not isinstance(var_name_suffix, str):
        raise TypeError("var_name_suffix 必须是字符串")
    
    mat_data = {}
    processed_files = 0
    error_files = 0
    success_list = []
    error_list = []
    details = {}

    # 如果未指定输出目录，使用输入目录
    if output_dir is None:
        output_dir = folder_path
    else:
        # 确保输出目录存在
        ensure_directory(output_dir)

    if verbose:
        print(f"开始处理文件夹: {folder_path}")
        print(f"输出目录: {output_dir}")
        print(f"MAT文件名: {mat_filename}")
        print(f"缩放因子: {scale_factor}")
        print(f"是否缩放原始数据: {scale_original}")
        print()

    start_time = time.time()

    for filename in os.listdir(folder_path):
        if filename.endswith('.xlsx'):
            excel_path = os.path.join(folder_path, filename)
            file_details = {
                'input_file': filename,
                'shape': None,
                'status': 'pending'
            }

            # 读取Excel文件
            try:
                # 对于大文件，使用低内存模式
                df = pd.read_excel(excel_path, header=None, engine='openpyxl')
            except Exception as e:
                if verbose:
                    print(f"错误: 无法读取文件 {filename} ({e})")
                error_files += 1
                error_list.append(filename)
                file_details['status'] = 'read_error'
                file_details['error_message'] = str(e)
                details[filename] = file_details
                continue

            try:
                # 转换为double矩阵
                matrix = df.values.astype(float)
                file_details['shape'] = matrix.shape
                
                # 对于大文件，显示处理信息
                if matrix.shape[0] > batch_size and verbose:
                    print(f"处理大文件: {filename} (共 {matrix.shape[0]} 行, {matrix.shape[1]} 列)")

                # 根据文件名进行数据处理
                if 'original' not in filename.lower() or scale_original:
                    matrix = matrix / scale_factor  # 缩放数据
                    if verbose:
                        print(f'数据已缩放: {filename} (缩放因子: {scale_factor})')
                else:
                    if verbose:
                        print(f'保持原始数据: {filename}')

                # 矩阵转置
                matrix = matrix.T
                if verbose:
                    print(f'已执行矩阵转置: {filename} -> 新维度 {matrix.shape}')

                # 生成带前缀的变量名
                base_name = os.path.splitext(filename)[0]
                base_name = re.sub(r'[^a-zA-Z0-9]', '_', base_name)
                parts = base_name.split('_', 1)
                existing_prefix = parts[0] if len(parts) == 2 else ''
                if existing_prefix and existing_prefix.isalpha():
                    if existing_prefix == var_name_prefix:
                        var_name = f"{base_name}_{var_name_suffix}"
                    else:
                        var_name = f"{var_name_prefix}_{parts[1]}_{var_name_suffix}"
                else:
                    var_name = f"{var_name_prefix}_{base_name}_{var_name_suffix}"

                # 处理重复变量名
                original_name = var_name
                counter = 1
                while var_name in mat_data:
                    var_name = f"{original_name}_{counter}"
                    counter += 1

                mat_data[var_name] = matrix
                if verbose:
                    print(f'已添加变量: {var_name}')
                processed_files += 1
                success_list.append(filename)
                file_details['status'] = 'success'
                file_details['variable_name'] = var_name

            except ValueError as e:
                if verbose:
                    print(f'错误: 文件 {filename} 包含非数值数据 ({e})')
                error_files += 1
                error_list.append(filename)
                file_details['status'] = 'value_error'
                file_details['error_message'] = str(e)
                details[filename] = file_details
                continue
            except Exception as e:
                if verbose:
                    print(f'错误: 处理文件 {filename} 时出错 ({e})')
                error_files += 1
                error_list.append(filename)
                file_details['status'] = 'process_error'
                file_details['error_message'] = str(e)
                details[filename] = file_details
                continue
            
            details[filename] = file_details

    # 保存.mat文件
    end_time = time.time()
    total_time = end_time - start_time
    
    if mat_data:
        mat_path = os.path.join(output_dir, mat_filename)
        savemat(mat_path, mat_data)
        if verbose:
            print(f'MAT文件已保存至: {mat_path}')
            print(f'成功处理: {processed_files} 个文件')
            print(f'错误文件: {error_files} 个文件')
            print(f'总耗时: {total_time:.2f} 秒')
    else:
        if verbose:
            print('没有成功处理的Excel文件，跳过MAT文件创建')
            print(f'总耗时: {total_time:.2f} 秒')
    
    return {
        'processed_files': processed_files,
        'error_files': error_files,
        'success_list': success_list,
        'error_list': error_list,
        'details': details,
        'total_time': total_time
    }

def main():
    try:
        folder_path = input("请输入文件夹路径：").strip()

        if not os.path.isdir(folder_path):
            print("错误: 指定的路径不存在或不是目录")
            return

        # 第一步：转换txt到excel（强制数值格式）
        result = txt_to_excel(folder_path)
        
        # 第二步：转换excel到mat（带转置和前缀）
        if result['processed_files'] > 0:
            print("\n开始转换Excel文件到MAT文件...")
            ## mat_result = excel_to_mat(folder_path)
            mat_result = excel_to_mat(
                folder_path,
                mat_filename=f"EMGStandardData{datetime.now().strftime('%Y%m%d')}.mat",
                scale_factor=1e6,
                var_name_prefix="EMGBuffer",  # 自定义前缀
                var_name_suffix="4ch"  # 自定义后缀
            )
            # 显示MAT转换结果
            print(f"\nMAT转换结果：")
            print(f"成功处理: {mat_result['processed_files']} 个文件")
            print(f"错误文件: {mat_result['error_files']} 个文件")
            print(f"总耗时: {mat_result['total_time']:.2f} 秒")
        else:
            print("\n没有成功处理的Excel文件，跳过MAT文件转换")
    except Exception as e:
        print(f"错误: 程序执行过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # 确保已安装依赖库：
    # pip install pandas openpyxl scipy
    main()