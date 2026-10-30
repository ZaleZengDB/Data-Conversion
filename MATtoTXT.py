import os
import time
import traceback
import pandas as pd
from scipy.io import loadmat
import re
import numpy as np


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


def validate_file_path(path, extension=None):
    """验证输入路径是否存在且为文件"""
    if not isinstance(path, str):
        raise TypeError("路径必须是字符串")
    if not os.path.isfile(path):
        raise ValueError(f"指定的路径不存在或不是文件: {path}")
    if extension and not path.endswith(extension):
        raise ValueError(f"指定的文件不是 {extension} 文件: {path}")


def format_time(seconds):
    """格式化时间为可读字符串"""
    return f"{seconds:.2f} 秒"

# 参考路径 C:/Users/Administrator/Desktop/data/EFT test/0415/2号机/testdata/EFTnewData.mat
# 参考路径 C:/Users/Administrator/Desktop/data/Standard EMG/Record261029/QueryData261029/EMGSigroiDataTemp.mat


def transform_var_name(var_name):
    """将变量名转换为输出文件名，例如 EMG_Sigroi_050us_01500uA -> QueryData_1.5mA_50us

    规则:
        - 丢弃 EMG_Sigroi 等前导段，统一以 QueryData 开头
        - 识别形如 050us 的段，去前导0 -> 50us
        - 识别形如 01500uA 的段，数值/1000 转为 mA -> 1.5mA (03000uA -> 3mA)
        - 输出顺序为 QueryData_mA_us，并保留 us/uA 之后的尾段(如 Whole)
        - 无法识别 us/uA 段时回退为合法化原变量名
    """
    parts = var_name.split('_')
    us_idx = None
    ua_idx = None
    us_part = None
    ua_part = None
    for i, p in enumerate(parts):
        m = re.match(r'^0*(\d+)us$', p, re.IGNORECASE)
        if m and us_idx is None:
            us_idx = i
            us_part = m.group(1) + 'us'
            continue
        m = re.match(r'^0*(\d+)uA$', p, re.IGNORECASE)
        if m and ua_idx is None:
            ua_idx = i
            val = int(m.group(1))
            ua_part = f"{val / 1000:g}mA"
    if ua_part and us_part:
        tail = parts[max(us_idx, ua_idx) + 1:]
        tail_str = '_' + '_'.join(tail) if tail else ''
        return f"QueryData_{ua_part}_{us_part}{tail_str}"
    return re.sub(r'[^a-zA-Z0-9]', '_', var_name)


def mat_to_excel(mat_path, output_folder, batch_size=1000, verbose=True):
    """将.mat文件中的变量转置后保存为Excel文件
    
    参数:
        mat_path: str - MAT文件路径
        output_folder: str - 输出Excel文件的目录
        batch_size: int - 批处理大小，用于处理大文件，默认为1000行
        verbose: bool - 是否显示详细日志，默认为True
    
    返回:
        dict - 包含处理结果的字典，包括：
            - processed_vars: 成功处理的变量数
            - error_vars: 错误变量数
            - success_list: 成功处理的变量列表
            - error_list: 错误变量列表
            - details: 详细处理信息
            - total_time: 总处理时间
    """
    # 输入验证
    validate_file_path(mat_path, '.mat')
    
    if not isinstance(output_folder, str):
        raise TypeError("output_folder 必须是字符串")
    
    if not isinstance(batch_size, int):
        raise TypeError("batch_size 必须是整数")
    
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于0")
    
    if not isinstance(verbose, bool):
        raise TypeError("verbose 必须是布尔值")
    
    # 确保输出目录存在
    ensure_directory(output_folder)
    
    processed_vars = 0
    error_vars = 0
    success_list = []
    error_list = []
    details = {}
    
    if verbose:
        print(f"开始处理MAT文件: {mat_path}")
        print(f"输出目录: {output_folder}")
        print()
    
    start_time = time.time()
    
    # 加载MAT文件
    try:
        mat_data = loadmat(mat_path)
    except Exception as e:
        if verbose:
            print(f"错误: 无法读取MAT文件 ({e})")
        return {
            'processed_vars': 0,
            'error_vars': 0,
            'success_list': [],
            'error_list': [],
            'details': {},
            'total_time': time.time() - start_time
        }

    # 过滤MATLAB系统变量
    valid_vars = [k for k in mat_data.keys() if not k.startswith('__')]
    
    if verbose:
        print(f"找到 {len(valid_vars)} 个有效变量")

    for var_name in valid_vars:
        var_details = {
            'variable_name': var_name,
            'shape': None,
            'status': 'pending'
        }
        
        data = mat_data[var_name]

        # 验证数据类型
        if not isinstance(data, np.ndarray):
            if verbose:
                print(f"跳过非数组变量: {var_name}")
            error_vars += 1
            error_list.append(var_name)
            var_details['status'] = 'not_array'
            details[var_name] = var_details
            continue
        
        if data.ndim != 2:
            if verbose:
                print(f"跳过非二维数组变量: {var_name} (维度: {data.shape})")
            error_vars += 1
            error_list.append(var_name)
            var_details['status'] = 'not_2d_array'
            var_details['shape'] = data.shape
            details[var_name] = var_details
            continue

        try:
            # 执行逆转置（恢复原始维度）
            original_matrix = data.T  # 转置恢复原始方向
            var_details['shape'] = original_matrix.shape
            
            # 对于大文件，显示处理信息
            if original_matrix.shape[0] > batch_size and verbose:
                print(f"处理大变量: {var_name} (共 {original_matrix.shape[0]} 行, {original_matrix.shape[1]} 列)")

            # 创建DataFrame并保存Excel
            df = pd.DataFrame(original_matrix)

            # 生成合法文件名
            clean_name = transform_var_name(var_name)
            excel_filename = f"{clean_name}.xlsx"
            excel_path = os.path.join(output_folder, excel_filename)

            # 优化Excel写入
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, header=False)
            
            if verbose:
                print(f"已生成: {excel_filename} (维度: {original_matrix.shape})")
            
            processed_vars += 1
            success_list.append(var_name)
            var_details['status'] = 'success'
            var_details['output_file'] = excel_filename

        except Exception as e:
            if verbose:
                print(f"错误: 处理变量 {var_name} 失败 ({e})")
            error_vars += 1
            error_list.append(var_name)
            var_details['status'] = 'error'
            var_details['error_message'] = str(e)
        
        details[var_name] = var_details
    
    end_time = time.time()
    total_time = end_time - start_time
    
    if verbose:
        print(f"\n处理完成！")
        print(f"总耗时: {total_time:.2f} 秒")
        print(f"成功处理: {processed_vars} 个变量")
        print(f"错误变量: {error_vars} 个变量")
    
    return {
        'processed_vars': processed_vars,
        'error_vars': error_vars,
        'success_list': success_list,
        'error_list': error_list,
        'details': details,
        'total_time': total_time
    }

def excel_to_txt(excel_folder, txt_folder, delimiter='/', batch_size=1000, verbose=True):
    """将Excel文件转换为TXT文件
    
    参数:
        excel_folder: str - 包含Excel文件的文件夹路径
        txt_folder: str - 输出TXT文件的目录
        delimiter: str - TXT文件中数据的分隔符，默认为'/'
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
    validate_input_path(excel_folder)
    
    if not isinstance(txt_folder, str):
        raise TypeError("txt_folder 必须是字符串")
    
    if not isinstance(delimiter, str):
        raise TypeError("delimiter 必须是字符串")
    
    if not isinstance(batch_size, int):
        raise TypeError("batch_size 必须是整数")
    
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于0")
    
    if not isinstance(verbose, bool):
        raise TypeError("verbose 必须是布尔值")
    
    # 确保输出目录存在
    ensure_directory(txt_folder)
    
    processed_files = 0
    error_files = 0
    success_list = []
    error_list = []
    details = {}
    
    if verbose:
        print(f"开始处理Excel文件: {excel_folder}")
        print(f"输出目录: {txt_folder}")
        print(f"分隔符: '{delimiter}'")
        print()
    
    start_time = time.time()
    
    for filename in os.listdir(excel_folder):
        if filename.endswith('.xlsx'):
            excel_path = os.path.join(excel_folder, filename)
            txt_filename = filename.replace('.xlsx', '.txt')
            txt_path = os.path.join(txt_folder, txt_filename)
            
            file_details = {
                'input_file': filename,
                'output_file': txt_filename,
                'status': 'pending'
            }

            try:
                # 读取Excel文件
                df = pd.read_excel(excel_path, header=None, engine='openpyxl')

                # 转换为数值矩阵
                matrix = df.values.astype(float)
                file_details['shape'] = matrix.shape
                
                # 对于大文件，显示处理信息
                if matrix.shape[0] > batch_size and verbose:
                    print(f"处理大文件: {filename} (共 {matrix.shape[0]} 行, {matrix.shape[1]} 列)")

                # 写入TXT文件
                with open(txt_path, 'w', encoding='utf-8') as f:
                    for row in matrix:
                        line = delimiter.join(f"{x:.10f}" for x in row)
                        f.write(line + '\n')

                if verbose:
                    print(f"已转换: {filename} -> {txt_filename}")
                
                processed_files += 1
                success_list.append(filename)
                file_details['status'] = 'success'

            except Exception as e:
                if verbose:
                    print(f"错误: 处理文件 {filename} 失败 ({e})")
                error_files += 1
                error_list.append(filename)
                file_details['status'] = 'error'
                file_details['error_message'] = str(e)
            
            details[filename] = file_details
    
    end_time = time.time()
    total_time = end_time - start_time
    
    if verbose:
        print(f"\n处理完成！")
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

def main():
    try:
        # 输入参数
        mat_path = input("请输入MAT文件路径：").strip()
        output_base = input("请输入输出目录路径：").strip()

        # 创建子目录
        excel_folder = os.path.join(output_base, 'excel_output')
        txt_folder = os.path.join(output_base, 'txt_output')

        # 执行转换流程
        print("\n=== MAT转Excel ===")
        mat_result = mat_to_excel(mat_path, excel_folder)

        print("\n=== Excel转TXT ===")
        txt_result = excel_to_txt(excel_folder, txt_folder)

        # 显示转换结果
        print("\n=== 转换流程全部完成！ ===")
        print(f"MAT转Excel: 成功 {mat_result['processed_vars']} 个变量, 错误 {mat_result['error_vars']} 个变量")
        print(f"Excel转TXT: 成功 {txt_result['processed_files']} 个文件, 错误 {txt_result['error_files']} 个文件")
        print(f"总耗时: {mat_result['total_time'] + txt_result['total_time']:.2f} 秒")

    except Exception as e:
        print(f"错误: 程序执行过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # 需要预先安装：
    # pip install pandas openpyxl scipy
    main()