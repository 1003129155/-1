"""
jietuba_smart_stitch.py - 智能图片拼接模块

使用ORB特征点匹配 + RANSAC，自动识别重叠区域并智能拼接
这是专业图像拼接软件的标准方法（Photoshop、Hugin等都用这个）

最新优化版本 - 2025-10-29 Y轴几何约束升级版
================================

🎯 新增功能 (2025-10-29):
  ⭐ Y轴几何约束验证
     - 检测规则：Y轴偏移不应为负数（长截图向下滚动，不会向上）
     - 异常检测：当median_offset < -10px时，自动触发备选方案
     - 多策略重试：标准搜索 → 扩大搜索 → 全图搜索 → 模板匹配
     - 提高准确性：避免误检测导致的错误拼接

  ⭐ 自动过滤重复图片
     - 检测规则：如果图i与图i+1的重复率>60%，且图i与图i+2的重复率>20%，则跳过图i+1
     - 应用场景：网页滚动截图时的重复帧、动态广告导致的重复内容
     - 提高拼接质量，减少冗余内容

  ⭐ 两两配对拼接策略 (pairwise) - 
     - 分治法：每轮将相邻图片两两配对拼接
     - 优势：图片大小相近，特征点分布均衡，减少累积误差
     - 示例：8张图 → 4张 → 2张 → 1张
  
  📌 保留传统策略 (sequential)
     - 顺序累积拼接
     - 适用于简单场景

核心算法:
  ✅ ORB特征点匹配 - 快速、鲁棒
  ✅ Y轴几何约束 - 🆕 防止负数偏移的误检测
  ✅ 多策略重试机制 - 🆕 自动扩大搜索范围
  ✅ 重复图片检测 - 自动过滤冗余帧
  ✅ 自适应特征检测 - 根据纹理丰富度自动调整策略
  ✅ MAD-based RANSAC - 更鲁棒的异常值过滤
  ✅ 几何约束验证 - X轴偏移约束(垂直拼接)
  ✅ 多维度置信度评估 - 6个维度综合评分
  ✅ 模板匹配后备 - 特征点失败时自动降级

优化点:
  🚀 Y轴约束: 🆕 检测负数偏移，自动重试更大范围
  🚀 多策略搜索: 🆕 标准 → 扩大 → 全图 → 模板匹配
  🚀 重复过滤: 智能检测并移除重复图片
  🚀 特征点数量: 1500 → 2000
  🚀 纹理检测: 自动识别低纹理区域
  🚀 边缘增强: 低纹理时使用直方图均衡化
  🚀 X轴约束: 过滤不符合垂直拼接的匹配点
  🚀 MAD异常值检测: 比四分位数更鲁棒
  🚀 空间分布检查: 避免特征点聚集
  🚀 置信度6维度: 更全面的质量评估
  🚀 多层降级: 特征点 → 模板匹配 → 简单拼接
  🚀 两两配对: 减少累积误差，匹配更准确

置信度计算:
  - 匹配数量 (25%): 50个匹配点满分
  - 稳定性 (25%): 标准差越小越好
  - 匹配距离 (15%): 特征描述符距离
  - 内点比例 (15%): RANSAC内点比例
  - X轴约束 (10%): X轴偏移应接近0
  - 空间分布 (10%): 匹配点应均匀分布

适用场景:
  📱 网页长截图 - 处理动态广告、自动过滤重复帧
  💬 聊天记录 - 精确对齐文字
  📄 文档拼接 - 无缝拼接
  🎨 低纹理图像 - 纯色、渐变背景
"""

import cv2
import numpy as np
from PIL import Image
from typing import List, Union, Tuple, Optional
from pathlib import Path


def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """将PIL Image转换为OpenCV格式"""
    if pil_image.mode == 'RGB':
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    elif pil_image.mode == 'RGBA':
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGRA)
    else:
        return np.array(pil_image.convert('RGB'))


def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    """将OpenCV图像转换为PIL Image"""
    if len(cv2_image.shape) == 2:  # 灰度图
        return Image.fromarray(cv2_image)
    elif cv2_image.shape[2] == 3:  # BGR
        return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))
    elif cv2_image.shape[2] == 4:  # BGRA
        return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGRA2RGBA))
    else:
        return Image.fromarray(cv2_image)


def _detect_texture_level(gray_image: np.ndarray) -> float:
    """
    检测图像纹理丰富度
    
    Args:
        gray_image: 灰度图像
        
    Returns:
        纹理分数 0.0-1.0 (越高越丰富)
    """
    # 使用Laplacian方差评估纹理
    laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
    variance = laplacian.var()
    
    # 归一化到0-1
    texture_score = min(variance / 1000.0, 1.0)
    
    return texture_score


def _adaptive_feature_detection(gray1: np.ndarray, gray2: np.ndarray,
                                base_nfeatures: int = 2000) -> Tuple:
    """
    自适应特征检测 - 根据纹理丰富度调整检测策略
    
    Args:
        gray1, gray2: 灰度图像
        base_nfeatures: 基础特征点数量
        
    Returns:
        (kp1, des1, kp2, des2, method_used)
    """
    # 检测纹理水平
    texture1 = _detect_texture_level(gray1)
    texture2 = _detect_texture_level(gray2)
    avg_texture = (texture1 + texture2) / 2
    
    print(f"   纹理丰富度: img1={texture1:.3f}, img2={texture2:.3f}, avg={avg_texture:.3f}")
    
    # 根据纹理丰富度调整策略
    if avg_texture > 0.3:
        # 纹理丰富 - 使用标准ORB
        print(f"   使用标准ORB检测器")
        orb = cv2.ORB_create(
            nfeatures=base_nfeatures,
            scaleFactor=1.2,
            nlevels=8,
            edgeThreshold=10,
            firstLevel=0,
            WTA_K=2,
            scoreType=cv2.ORB_HARRIS_SCORE,
            patchSize=31,
            fastThreshold=15
        )
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)
        return kp1, des1, kp2, des2, "ORB"
        
    else:
        # 纹理稀疏 - 使用更敏感的检测器 + 边缘增强
        print(f"   纹理稀疏,使用增强ORB + 边缘增强")
        
        # 边缘增强
        gray1_enhanced = cv2.equalizeHist(gray1)
        gray2_enhanced = cv2.equalizeHist(gray2)
        
        # 更敏感的ORB设置
        orb = cv2.ORB_create(
            nfeatures=int(base_nfeatures * 1.5),  # 增加特征点
            scaleFactor=1.15,  # 更细的尺度
            nlevels=10,        # 更多尺度层级
            edgeThreshold=5,   # 更低的边缘阈值
            firstLevel=0,
            WTA_K=2,
            scoreType=cv2.ORB_HARRIS_SCORE,
            patchSize=31,
            fastThreshold=10   # 更敏感的FAST阈值
        )
        
        kp1, des1 = orb.detectAndCompute(gray1_enhanced, None)
        kp2, des2 = orb.detectAndCompute(gray2_enhanced, None)
        
        return kp1, des1, kp2, des2, "ORB-Enhanced"


def _template_matching_fallback(img1: np.ndarray, img2: np.ndarray,
                                overlap_ratio: float = 0.3) -> Tuple[Optional[int], float]:
    """
    模板匹配后备方案 - 用于特征点匹配完全失败时
    
    Args:
        img1: 第一张图片
        img2: 第二张图片
        overlap_ratio: 预估重叠比例
        
    Returns:
        (offset_y, confidence)
    """
    try:
        print(f"   🔄 启用模板匹配后备方案")
        
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        
        # 转换为灰度图
        if len(img1.shape) == 3:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        else:
            gray1 = img1
            gray2 = img2
        
        # 预估重叠区域
        overlap_height = int(min(h1, h2) * overlap_ratio)
        if overlap_height < 50:
            overlap_height = min(100, min(h1, h2) // 2)
        
        # 从img2顶部取模板
        template = gray2[:overlap_height, :]
        
        # 在img1底部搜索
        search_height = int(h1 * 0.6)  # 在底部60%搜索
        search_region = gray1[-search_height:, :]
        
        # 模板匹配
        result = cv2.matchTemplate(search_region, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        # 计算offset_y
        match_y_in_search = max_loc[1]
        search_start = h1 - search_height
        offset_y = search_start + match_y_in_search
        
        # 置信度 = 匹配分数
        confidence = float(max_val) * 0.7  # 降权,因为是后备方案
        
        print(f"   模板匹配: offset_y={offset_y}, confidence={confidence:.3f}, score={max_val:.3f}")
        
        return offset_y, confidence
        
    except Exception as e:
        print(f"   ❌ 模板匹配失败: {e}")
        return None, 0.0




def find_overlap_region(img1: np.ndarray, img2: np.ndarray, 
                       overlap_ratio: float = 0.3,
                       min_match_count: int = 10,
                       use_multi_scale: bool = True,
                       scroll_distance: int = None) -> Tuple[Optional[int], float]:
    """
    使用ORB特征点匹配找到两张图片的重叠区域（支持滚动距离辅助）
    
    优化版本 (2025-11-13 混合方案升级):
    - 🆕 滚动距离辅助：使用物理滚动距离缩小搜索范围，提高准确性
    - 🆕 Y轴几何约束验证 (Y偏移不应为负数)
    - 🆕 异常检测 + 自动重试机制 (扩大搜索区域)
    - 多尺度特征检测(提高鲁棒性)
    - 几何约束(X轴偏移应接近0)
    - 改进的RANSAC异常值过滤
    - 匹配点空间分布检查
    
    Args:
        img1: 第一张图片（上面的）
        img2: 第二张图片（下面的）
        overlap_ratio: 搜索范围比例（不是预估重叠，而是搜索区域大小）
        min_match_count: 最小匹配点数量
        use_multi_scale: 是否使用多尺度检测
        scroll_distance: 🆕 滚动距离（像素），用于缩小搜索范围
        
    Returns:
        (offset_y, confidence): Y轴偏移量和置信度
    """
    # 🆕 根据是否有滚动距离信息选择搜索策略
    if scroll_distance is not None and scroll_distance > 0:
        # 有滚动距离信息：使用精确搜索
        h1 = img1.shape[0]
        
        # 🔧 滚动距离校准：实际图像偏移通常小于理论滚动距离
        # 根据经验，实际偏移约为滚动距离的50-70%
        scroll_efficiency = 0.6  # 可以根据实际效果调整
        estimated_offset = int(scroll_distance * scroll_efficiency)
        
        print(f"📏 使用滚动距离辅助: {scroll_distance}px → 估算offset={estimated_offset} (校准后，效率={scroll_efficiency})")
        print(f"   逻辑: 滚动{scroll_distance}px × {scroll_efficiency} = img2顶部对应img1第{estimated_offset}px位置")
        
        strategies = [
            {'name': '精确搜索(±15px)', 'search_ratio_multiplier': 2.0, 'use_full_height': False, 
             'centered_search': True, 'center_offset': estimated_offset, 'search_range': 15},
            {'name': '扩大搜索(±30px)', 'search_ratio_multiplier': 2.0, 'use_full_height': False,
             'centered_search': True, 'center_offset': estimated_offset, 'search_range': 30},
            {'name': '后备搜索(±60px)', 'search_ratio_multiplier': 2.0, 'use_full_height': False,
             'centered_search': True, 'center_offset': estimated_offset, 'search_range': 60},
        ]
    else:
        # 无滚动距离：使用传统大范围搜索
        strategies = [
            {'name': '标准策略', 'search_ratio_multiplier': 2.0, 'use_full_height': False},
            {'name': '扩大搜索', 'search_ratio_multiplier': 3.0, 'use_full_height': False},
            {'name': '全图搜索', 'search_ratio_multiplier': 1.0, 'use_full_height': True},
        ]
    
    for strategy_idx, strategy in enumerate(strategies):
        try:
            result = _try_find_overlap(
                img1, img2, overlap_ratio, min_match_count, 
                strategy, strategy_idx
            )
            
            if result is not None:
                offset_y, confidence, y_median_offset = result
                
                # 🆕 验证Y偏移合理性 (不应为负数，除非误差很小)
                if y_median_offset < -10:
                    print(f"   ⚠️ Y偏移异常 (median={y_median_offset:.1f}px < -10px)，尝试下一个策略...")
                    if strategy_idx < len(strategies) - 1:
                        continue  # 尝试下一个策略
                    else:
                        print(f"   ⚠️ 所有策略均失败，降级到模板匹配")
                        return _template_matching_fallback(img1, img2, overlap_ratio)
                
                # Y偏移合理，返回结果
                return offset_y, confidence
            
            # 当前策略失败，尝试下一个
            if strategy_idx < len(strategies) - 1:
                print(f"   ⚠️ {strategy['name']}失败，尝试下一个策略...")
                continue
        
        except Exception as e:
            print(f"   ❌ {strategy['name']}出错: {e}")
            if strategy_idx < len(strategies) - 1:
                continue
    
    # 所有策略都失败，使用模板匹配
    print(f"   ⚠️ 所有特征匹配策略失败，降级到模板匹配")
    return _template_matching_fallback(img1, img2, overlap_ratio)


def _try_find_overlap(img1: np.ndarray, img2: np.ndarray,
                     overlap_ratio: float,
                     min_match_count: int,
                     strategy: dict,
                     strategy_idx: int) -> Optional[Tuple[int, float, float]]:
    """
    尝试使用指定策略查找重叠区域
    
    Returns:
        (offset_y, confidence, y_median_offset) 或 None
    """
    try:
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        
        if strategy_idx == 0:
            print(f"\n🔍 特征点匹配: img1={h1}x{w1}, img2={h2}x{w2}")
        print(f"   策略: {strategy['name']}")
        
        # 🆕 1. 根据策略提取搜索区域（支持centered_search）
        if strategy.get('centered_search', False):
            # 精确搜索模式：在估算位置附近搜索重叠区域
            center_offset = strategy['center_offset']
            search_range = strategy['search_range']
            
            # 🔧 修正搜索区域逻辑：搜索重叠区域，而不是任意区域
            # offset=155px 意味着 img2顶部对应img1第155px位置
            # 重叠区域是：img1[155:518] 对应 img2[0:363]
            
            # img1搜索区域：从offset开始，允许±search_range的误差
            region1_start = max(0, center_offset - search_range)
            region1_end = min(h1, h1)  # 搜索到img1底部
            
            # img2搜索区域：从顶部开始，高度对应重叠区域
            overlap_height = h1 - center_offset + search_range
            region2_end = min(h2, overlap_height)
            
            region1 = img1[region1_start:region1_end, :]
            region2 = img2[0:region2_end, :]
            
            print(f"   🎯 中心搜索: offset={center_offset}px, 范围=±{search_range}px")
            print(f"   搜索区域: region1=[{region1_start}:{region1_end}], region2=[0:{region2_end}]")
            print(f"   逻辑: img1[{center_offset}:] 应该匹配 img2[0:], 允许±{search_range}px误差")
            
        elif strategy['use_full_height']:
            # 全图搜索
            region1 = img1
            region2 = img2
            region1_start = 0
        else:
            # 部分搜索（传统方式）
            search_ratio = max(0.5, overlap_ratio * strategy['search_ratio_multiplier'])
            search_height1 = int(h1 * search_ratio)
            search_height2 = int(h2 * search_ratio)
            
            region1 = img1[-search_height1:, :]  # img1的下半部分
            region2 = img2[:search_height2, :]   # img2的上半部分
            region1_start = h1 - search_height1
        
        # 转换为灰度图
        if len(region1.shape) == 3:
            gray1 = cv2.cvtColor(region1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(region2, cv2.COLOR_BGR2GRAY)
        else:
            gray1 = region1
            gray2 = region2
        
        print(f"   搜索区域: region1={gray1.shape}, region2={gray2.shape}")
        
        # 2. 自适应特征检测(根据纹理丰富度选择策略)
        kp1, des1, kp2, des2, method = _adaptive_feature_detection(
            gray1, gray2, base_nfeatures=2000
        )
        
        if des1 is None or des2 is None or len(kp1) < min_match_count:
            print(f"   ❌ 特征点不足: img1={len(kp1) if kp1 else 0}, img2={len(kp2) if kp2 else 0}")
            return None
        
        print(f"   特征点({method}): img1={len(kp1)}, img2={len(kp2)}")
        
        # 3. 特征匹配（BFMatcher）
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        try:
            matches = bf.knnMatch(des1, des2, k=2)
        except cv2.error as e:
            print(f"   ❌ 匹配失败: {e}")
            return None
        
        # 4. Lowe's ratio test 筛选好的匹配
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:  # Lowe推荐的阈值
                    good_matches.append(m)
        
        print(f"   匹配: 总数={len(matches)}, 优质={len(good_matches)}")
        
        if len(good_matches) < min_match_count:
            print(f"   ⚠️ 优质匹配过少 ({len(good_matches)} < {min_match_count})")
            return None
        
        # 5. 提取匹配点坐标
        pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
        pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
        
        # 🆕 6. 几何约束验证 - 垂直拼接时X轴偏移应接近0
        x_offsets = pts1[:, 0] - pts2[:, 0]
        x_median = np.median(x_offsets)
        x_std = np.std(x_offsets)
        
        # 过滤X轴偏移异常的点(超过3倍标准差)
        x_inliers_mask = np.abs(x_offsets - x_median) < 3 * max(x_std, 5)
        
        if np.sum(x_inliers_mask) < min_match_count:
            print(f"   ⚠️ X轴约束过滤后匹配点不足: {np.sum(x_inliers_mask)}")
            x_penalty = 0.5
        else:
            # 应用X轴过滤
            pts1 = pts1[x_inliers_mask]
            pts2 = pts2[x_inliers_mask]
            good_matches = [m for i, m in enumerate(good_matches) if x_inliers_mask[i]]
            x_penalty = 1.0
            print(f"   ✅ X轴约束过滤: 保留 {len(good_matches)} 个匹配点 (X_median={x_median:.1f}px, X_std={x_std:.1f}px)")
        
        # 🆕 7. 改进的Y轴偏移计算 - 使用RANSAC思想
        y_offsets = pts1[:, 1] - pts2[:, 1]
        
        # 使用改进的异常值过滤(MAD - Median Absolute Deviation)
        if len(y_offsets) >= 4:
            y_median = np.median(y_offsets)
            mad = np.median(np.abs(y_offsets - y_median))
            
            # MAD-based 异常值检测(更鲁棒)
            if mad > 0:
                modified_z_scores = 0.6745 * (y_offsets - y_median) / mad
                y_inliers_mask = np.abs(modified_z_scores) < 3.5
            else:
                # MAD为0说明所有点几乎一致,直接使用
                y_inliers_mask = np.ones(len(y_offsets), dtype=bool)
            
            if np.sum(y_inliers_mask) >= 3:
                y_filtered = y_offsets[y_inliers_mask]
                median_offset = np.median(y_filtered)
                std_offset = np.std(y_filtered)
                inlier_ratio = np.sum(y_inliers_mask) / len(y_offsets)
                print(f"   Y轴RANSAC: 内点比例={inlier_ratio:.1%}, 有效点={np.sum(y_inliers_mask)}/{len(y_offsets)}")
            else:
                # RANSAC失败,回退到四分位数
                y_sorted = np.sort(y_offsets)
                q1_idx = len(y_sorted) // 4
                q3_idx = 3 * len(y_sorted) // 4
                y_filtered = y_sorted[q1_idx:q3_idx]
                median_offset = np.median(y_filtered)
                std_offset = np.std(y_filtered)
                inlier_ratio = 0.5
                print(f"   Y轴四分位: 使用中间50%的点")
        else:
            median_offset = np.median(y_offsets)
            std_offset = np.std(y_offsets)
            inlier_ratio = 1.0
        
        print(f"   Y轴偏移: median={median_offset:.1f}px, std={std_offset:.1f}px")
        
        # 🆕 8. 计算实际offset_y（从img1顶部算起）
        offset_y = int(region1_start + median_offset)
        
        # 🆕 9. 改进的置信度计算（多维度综合评估）
        # 9.1 匹配数量置信度
        num_confidence = min(len(good_matches) / 50.0, 1.0)
        
        # 9.2 稳定性置信度(标准差)
        std_confidence = max(0, 1.0 - std_offset / 50.0)
        
        # 9.3 匹配距离置信度
        avg_distance = np.mean([m.distance for m in good_matches])
        dist_confidence = max(0, 1.0 - avg_distance / 100.0)
        
        # 🆕 9.4 内点比例置信度
        inlier_confidence = inlier_ratio
        
        # 🆕 9.5 X轴约束置信度
        x_constraint_confidence = 1.0 if abs(x_median) < 10 and x_std < 5 else max(0, 1.0 - abs(x_median) / 50.0)
        
        # 🆕 9.6 空间分布置信度(匹配点应均匀分布,避免聚集)
        if len(good_matches) >= 10:
            pts1_y = pts1[:, 1]
            y_range = np.max(pts1_y) - np.min(pts1_y)
            y_coverage = y_range / gray1.shape[0] if gray1.shape[0] > 0 else 0
            spatial_confidence = min(y_coverage / 0.3, 1.0)  # 期望覆盖至少30%的区域
        else:
            spatial_confidence = 0.5
        
        # 综合置信度(加权平均)
        confidence = (
            num_confidence * 0.25 +          # 匹配数量 25%
            std_confidence * 0.25 +          # 稳定性 25%
            dist_confidence * 0.15 +         # 距离 15%
            inlier_confidence * 0.15 +       # 内点比例 15%
            x_constraint_confidence * 0.10 + # X轴约束 10%
            spatial_confidence * 0.10        # 空间分布 10%
        )
        
        confidence *= x_penalty  # 应用X轴约束惩罚
        
        print(f"   置信度: {confidence:.3f}")
        print(f"      匹配={num_confidence:.2f}, 稳定={std_confidence:.2f}, 距离={dist_confidence:.2f}")
        print(f"      内点={inlier_confidence:.2f}, X约束={x_constraint_confidence:.2f}, 分布={spatial_confidence:.2f}")
        
        # 🆕 滚动距离校准反馈（如果有滚动距离信息）
        if strategy.get('centered_search', False) and 'center_offset' in strategy:
            expected_offset = strategy['center_offset']
            actual_offset = offset_y
            offset_error = abs(actual_offset - expected_offset)
            
            print(f"   📊 滚动校准: 预期offset={expected_offset}px, 实际={actual_offset}px, 误差={offset_error}px")
            
            if offset_error <= 30:
                print(f"   ✅ 滚动校准良好: 误差在±30px范围内")
            elif offset_error <= 60:
                print(f"   ⚠️ 滚动校准偏差: 误差{offset_error}px, 建议调整滚动效率")
            else:
                print(f"   ❌ 滚动校准失效: 误差{offset_error}px过大")
        
        # 10. 验证合理性（改进的逻辑）
        overlap_height = h1 - offset_y
        
        # 10.1 基本合理性检查
        if overlap_height <= 0:
            print(f"   ❌ 无重叠 (overlap={overlap_height}px)")
            confidence *= 0.2
            return offset_y, confidence, median_offset
        
        if overlap_height >= h2:
            # 特殊情况：img2完全在img1范围内（最后一次很小的滚动）
            # 这是合理的！计算真实的重叠比例
            overlap_ratio_to_img2 = overlap_height / h2
            
            if overlap_ratio_to_img2 > 1.0:
                # img2完全包含在重叠区域内
                actual_new_height = offset_y + h2
                
                # 检查特征匹配的质量
                if len(good_matches) >= 50 and std_offset < 10:
                    # 特征匹配质量很好，相信这个结果
                    print(f"   ✅ 小滚动检测: offset_y={offset_y}, img2完全在重叠区域内")
                    print(f"      img2高度={h2}px, 重叠={overlap_height}px, 新增={h2-overlap_height}px")
                    # 不惩罚置信度
                    return offset_y, confidence, median_offset
                else:
                    print(f"   ⚠️ 重叠异常: {overlap_height}px >= img2高度 {h2}px，且匹配质量不足")
                    confidence *= 0.3
                    return offset_y, confidence, median_offset
        
        # 10.2 正常情况：计算重叠比例
        # 使用img2高度作为基准（更合理）
        overlap_ratio_to_img2 = overlap_height / h2
        
        if overlap_ratio_to_img2 < 0.05:
            # 重叠太少（<5%）
            print(f"   ⚠️ 重叠过少: {overlap_height}px ({overlap_ratio_to_img2:.1%})")
            confidence *= 0.7  # 轻微惩罚
        elif overlap_ratio_to_img2 > 0.95:
            # 重叠很大（>95%），但如果特征匹配好，可能是小滚动
            if len(good_matches) >= 30 and std_offset < 5:
                print(f"   ✅ 小滚动: offset_y={offset_y}, 重叠={overlap_height}px ({overlap_ratio_to_img2:.1%})")
                # 不惩罚
            else:
                print(f"   ⚠️ 重叠过大: {overlap_height}px ({overlap_ratio_to_img2:.1%})")
                confidence *= 0.6
        else:
            # 正常范围（5%-95%）
            print(f"   ✅ 重叠合理: offset_y={offset_y}, 高度={overlap_height}px ({overlap_ratio_to_img2:.1%})")
        
        return offset_y, confidence, median_offset
        
    except Exception as e:
        print(f"   ❌ 特征匹配异常: {e}")
        import traceback
        traceback.print_exc()
        return None

        
        if strategy_idx == 0:
            print(f"\n🔍 特征点匹配: img1={h1}x{w1}, img2={h2}x{w2}")
        print(f"   策略: {strategy['name']}")
        
        # 1. 根据策略提取搜索区域
        if strategy['use_full_height']:
            # 全图搜索
            region1 = img1
            region2 = img2
            region1_start = 0
        else:
            # 部分搜索
            search_ratio = max(0.5, overlap_ratio * strategy['search_ratio_multiplier'])
            search_height1 = int(h1 * search_ratio)
            search_height2 = int(h2 * search_ratio)
            
            region1 = img1[-search_height1:, :]  # img1的下半部分
            region2 = img2[:search_height2, :]   # img2的上半部分
            region1_start = h1 - search_height1
        
        # 转换为灰度图
        if len(region1.shape) == 3:
            gray1 = cv2.cvtColor(region1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(region2, cv2.COLOR_BGR2GRAY)
        else:
            gray1 = region1
            gray2 = region2
        
        print(f"   搜索区域: region1={gray1.shape}, region2={gray2.shape}")
        
        # 2. 自适应特征检测(根据纹理丰富度选择策略)
        kp1, des1, kp2, des2, method = _adaptive_feature_detection(
            gray1, gray2, base_nfeatures=2000
        )
        
        if des1 is None or des2 is None or len(kp1) < min_match_count:
            print(f"   ❌ 特征点不足: img1={len(kp1) if kp1 else 0}, img2={len(kp2) if kp2 else 0}")
            # 🆕 尝试模板匹配作为后备
            return _template_matching_fallback(img1, img2, overlap_ratio)
        
        print(f"   特征点({method}): img1={len(kp1)}, img2={len(kp2)}")
        
        # 3. 特征匹配（BFMatcher）
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        try:
            matches = bf.knnMatch(des1, des2, k=2)
        except cv2.error as e:
            print(f"   ❌ 匹配失败: {e}")
            return None, 0.0
        
        # 4. Lowe's ratio test 筛选好的匹配
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:  # Lowe推荐的阈值
                    good_matches.append(m)
        
        print(f"   匹配: 总数={len(matches)}, 优质={len(good_matches)}")
        
        if len(good_matches) < min_match_count:
            print(f"   ⚠️ 优质匹配过少 ({len(good_matches)} < {min_match_count})")
            # 🆕 尝试模板匹配作为后备
            if len(good_matches) < min_match_count // 2:
                return _template_matching_fallback(img1, img2, overlap_ratio)
            # 匹配点较少但不是完全没有,继续尝试
            return None, len(good_matches) / max(min_match_count, 1)
        
        # 5. 提取匹配点坐标
        pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
        pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
        
        # 🆕 6. 几何约束验证 - 垂直拼接时X轴偏移应接近0
        x_offsets = pts1[:, 0] - pts2[:, 0]
        x_median = np.median(x_offsets)
        x_std = np.std(x_offsets)
        
        # 过滤X轴偏移异常的点(超过3倍标准差)
        x_inliers_mask = np.abs(x_offsets - x_median) < 3 * max(x_std, 5)
        
        if np.sum(x_inliers_mask) < min_match_count:
            print(f"   ⚠️ X轴约束过滤后匹配点不足: {np.sum(x_inliers_mask)}")
            # 不完全拒绝,降低置信度
            x_penalty = 0.5
        else:
            # 应用X轴过滤
            pts1 = pts1[x_inliers_mask]
            pts2 = pts2[x_inliers_mask]
            good_matches = [m for i, m in enumerate(good_matches) if x_inliers_mask[i]]
            x_penalty = 1.0
            print(f"   ✅ X轴约束过滤: 保留 {len(good_matches)} 个匹配点 (X_median={x_median:.1f}px, X_std={x_std:.1f}px)")
        
        # 🆕 7. 改进的Y轴偏移计算 - 使用RANSAC思想
        y_offsets = pts1[:, 1] - pts2[:, 1]
        
        # 使用改进的异常值过滤(MAD - Median Absolute Deviation)
        if len(y_offsets) >= 4:
            y_median = np.median(y_offsets)
            mad = np.median(np.abs(y_offsets - y_median))
            
            # MAD-based 异常值检测(更鲁棒)
            if mad > 0:
                modified_z_scores = 0.6745 * (y_offsets - y_median) / mad
                y_inliers_mask = np.abs(modified_z_scores) < 3.5
            else:
                # MAD为0说明所有点几乎一致,直接使用
                y_inliers_mask = np.ones(len(y_offsets), dtype=bool)
            
            if np.sum(y_inliers_mask) >= 3:
                y_filtered = y_offsets[y_inliers_mask]
                median_offset = np.median(y_filtered)
                std_offset = np.std(y_filtered)
                inlier_ratio = np.sum(y_inliers_mask) / len(y_offsets)
                print(f"   Y轴RANSAC: 内点比例={inlier_ratio:.1%}, 有效点={np.sum(y_inliers_mask)}/{len(y_offsets)}")
            else:
                # RANSAC失败,回退到四分位数
                y_sorted = np.sort(y_offsets)
                q1_idx = len(y_sorted) // 4
                q3_idx = 3 * len(y_sorted) // 4
                y_filtered = y_sorted[q1_idx:q3_idx]
                median_offset = np.median(y_filtered)
                std_offset = np.std(y_filtered)
                inlier_ratio = 0.5
                print(f"   Y轴四分位: 使用中间50%的点")
        else:
            median_offset = np.median(y_offsets)
            std_offset = np.std(y_offsets)
            inlier_ratio = 1.0
        
        print(f"   Y轴偏移: median={median_offset:.1f}px, std={std_offset:.1f}px")
        
        # 🆕 8. 计算实际offset_y（从img1顶部算起）
        region1_start = h1 - search_height1
        offset_y = int(region1_start + median_offset)
        
        # 🆕 9. 改进的置信度计算（多维度综合评估）
        # 9.1 匹配数量置信度
        num_confidence = min(len(good_matches) / 50.0, 1.0)
        
        # 9.2 稳定性置信度(标准差)
        std_confidence = max(0, 1.0 - std_offset / 50.0)
        
        # 9.3 匹配距离置信度
        avg_distance = np.mean([m.distance for m in good_matches])
        dist_confidence = max(0, 1.0 - avg_distance / 100.0)
        
        # 🆕 9.4 内点比例置信度
        inlier_confidence = inlier_ratio
        
        # 🆕 9.5 X轴约束置信度
        x_constraint_confidence = 1.0 if abs(x_median) < 10 and x_std < 5 else max(0, 1.0 - abs(x_median) / 50.0)
        
        # 🆕 9.6 空间分布置信度(匹配点应均匀分布,避免聚集)
        if len(good_matches) >= 10:
            pts1_y = pts1[:, 1]
            y_range = np.max(pts1_y) - np.min(pts1_y)
            y_coverage = y_range / gray1.shape[0] if gray1.shape[0] > 0 else 0
            spatial_confidence = min(y_coverage / 0.3, 1.0)  # 期望覆盖至少30%的区域
        else:
            spatial_confidence = 0.5
        
        # 综合置信度(加权平均)
        confidence = (
            num_confidence * 0.25 +          # 匹配数量 25%
            std_confidence * 0.25 +          # 稳定性 25%
            dist_confidence * 0.15 +         # 距离 15%
            inlier_confidence * 0.15 +       # 内点比例 15%
            x_constraint_confidence * 0.10 + # X轴约束 10%
            spatial_confidence * 0.10        # 空间分布 10%
        )
        
        confidence *= x_penalty  # 应用X轴约束惩罚
        
        print(f"   置信度: {confidence:.3f}")
        print(f"      匹配={num_confidence:.2f}, 稳定={std_confidence:.2f}, 距离={dist_confidence:.2f}")
        print(f"      内点={inlier_confidence:.2f}, X约束={x_constraint_confidence:.2f}, 分布={spatial_confidence:.2f}")
        
        # 9. 验证合理性（改进的逻辑）
        overlap_height = h1 - offset_y
        
        # 9.1 基本合理性检查
        if overlap_height <= 0:
            print(f"   ❌ 无重叠 (overlap={overlap_height}px)")
            confidence *= 0.2
            return offset_y, confidence
        
        if overlap_height >= h2:
            # 特殊情况：img2完全在img1范围内（最后一次很小的滚动）
            # 这是合理的！计算真实的重叠比例
            overlap_ratio_to_img2 = overlap_height / h2
            
            if overlap_ratio_to_img2 > 1.0:
                # img2完全包含在重叠区域内
                actual_new_height = offset_y + h2
                
                # 检查特征匹配的质量
                if len(good_matches) >= 50 and std_offset < 10:
                    # 特征匹配质量很好，相信这个结果
                    print(f"   ✅ 小滚动检测: offset_y={offset_y}, img2完全在重叠区域内")
                    print(f"      img2高度={h2}px, 重叠={overlap_height}px, 新增={h2-overlap_height}px")
                    # 不惩罚置信度
                    return offset_y, confidence
                else:
                    print(f"   ⚠️ 重叠异常: {overlap_height}px >= img2高度 {h2}px，且匹配质量不足")
                    confidence *= 0.3
                    return offset_y, confidence
        
        # 9.2 正常情况：计算重叠比例
        # 使用img2高度作为基准（更合理）
        overlap_ratio_to_img2 = overlap_height / h2
        
        if overlap_ratio_to_img2 < 0.05:
            # 重叠太少（<5%）
            print(f"   ⚠️ 重叠过少: {overlap_height}px ({overlap_ratio_to_img2:.1%})")
            confidence *= 0.7  # 轻微惩罚
        elif overlap_ratio_to_img2 > 0.95:
            # 重叠很大（>95%），但如果特征匹配好，可能是小滚动
            if len(good_matches) >= 30 and std_offset < 5:
                print(f"   ✅ 小滚动: offset_y={offset_y}, 重叠={overlap_height}px ({overlap_ratio_to_img2:.1%})")
                # 不惩罚
            else:
                print(f"   ⚠️ 重叠过大: {overlap_height}px ({overlap_ratio_to_img2:.1%})")
                confidence *= 0.6
        else:
            # 正常范围（5%-95%）
            print(f"   ✅ 重叠合理: offset_y={offset_y}, 高度={overlap_height}px ({overlap_ratio_to_img2:.1%})")
        
        return offset_y, confidence
        
    except Exception as e:
        print(f"❌ 特征匹配失败: {e}")
        import traceback
        traceback.print_exc()
        return None, 0.0


def _pairwise_stitch_recursive(images: List[np.ndarray],
                               overlap_ratio: float,
                               min_confidence: float,
                               blend: bool,
                               level: int = 0,
                               scroll_distances: List[int] = None) -> np.ndarray:
    """
    递归式两两配对拼接(分治法)
    
    工作原理:
      第1轮: [img1+img2, img3+img4, img5+img6, ...]  <- 小图+小图
      第2轮: [result1+result2, result3+result4, ...]  <- 中图+中图  
      第3轮: [result1+result2]                        <- 大图+大图
    
    优势:
      ✅ 每次匹配的图片大小相近,特征点分布均衡
      ✅ 减少累积误差,避免小图与巨大累积图匹配
      ✅ 符合分治算法思想,更鲁棒
    
    Args:
        images: OpenCV格式的图片列表
        overlap_ratio: 搜索范围比例
        min_confidence: 最小置信度
        blend: 是否混合
        level: 递归层级(用于日志)
        scroll_distances: 每次截图之间的滚动距离(像素)
    
    Returns:
        拼接后的OpenCV图像
    """
    if len(images) == 1:
        return images[0]
    
    indent = "  " * level
    print(f"{indent}🔄 第{level+1}轮配对: {len(images)}张图片 → {(len(images)+1)//2}张结果")
    
    next_level_images = []
    
    # 两两配对拼接
    for i in range(0, len(images), 2):
        if i + 1 < len(images):
            # 有配对
            img1 = images[i]
            img2 = images[i + 1]
            h1, h2 = img1.shape[0], img2.shape[0]
            
            print(f"{indent}   📎 配对 {i//2+1}: img{i+1}({h1}px) + img{i+2}({h2}px)")
            
            # 🆕 获取当前配对的滚动距离(第i+1张的滚动距离)
            scroll_distance = None
            if scroll_distances and level == 0:  # 仅在第一轮使用原始滚动距离
                # images[i+1]对应cv2_images[i+1],其滚动距离为scroll_distances[i+1]
                if i + 1 < len(scroll_distances):
                    scroll_distance = scroll_distances[i + 1]
            
            # 使用特征点匹配
            offset_y, confidence = find_overlap_region(img1, img2, overlap_ratio, scroll_distance=scroll_distance)
            
            if offset_y is not None and confidence >= min_confidence:
                overlap_pixels = h1 - offset_y
                # 修复: 使用 >= 而不是 >, 允许完全重叠的情况
                if overlap_pixels > 0 and offset_y + h2 >= h1:
                    # 智能拼接
                    print(f"{indent}      ✅ 智能拼接: overlap={overlap_pixels}px, conf={confidence:.3f}")
                    result = _blend_stitch(img1, img2, offset_y, overlap_pixels, blend)
                    next_level_images.append(result)
                else:
                    # 无效重叠, 简单拼接
                    print(f"{indent}      ⚠️ 无效重叠, 简单拼接")
                    result = _simple_append(img1, img2)
                    next_level_images.append(result)
            else:
                # 匹配失败, 简单拼接
                conf_str = f"{confidence:.3f}" if confidence > 0 else "N/A"
                print(f"{indent}      ⚠️ 匹配失败 (conf={conf_str}), 简单拼接")
                result = _simple_append(img1, img2)
                next_level_images.append(result)
        else:
            # 奇数个, 最后一张单独保留
            print(f"{indent}   📌 保留: img{i+1} (无配对)")
            next_level_images.append(images[i])
    
    # 递归处理下一轮
    return _pairwise_stitch_recursive(
        next_level_images, 
        overlap_ratio, 
        min_confidence, 
        blend, 
        level + 1,
        scroll_distances=None  # 后续轮次不再使用滚动距离
    )


def _calculate_overlap_ratio(img1: np.ndarray, img2: np.ndarray, 
                            search_ratio: float = 0.5) -> float:
    """
    计算两张图片的重复率
    
    Args:
        img1: 第一张图片
        img2: 第二张图片
        search_ratio: 搜索范围比例
        
    Returns:
        重复率 (0.0-1.0)
    """
    try:
        h1, h2 = img1.shape[0], img2.shape[0]
        
        # 使用find_overlap_region计算重叠
        offset_y, confidence = find_overlap_region(img1, img2, search_ratio)
        
        print(f"   🔍 重复率计算: offset_y={offset_y}, confidence={confidence:.3f}")
        
        if offset_y is None or confidence < 0.3:
            print(f"   ❌ 匹配失败: offset_y={offset_y}, confidence={confidence}")
            return 0.0
        
        # 计算重叠像素
        overlap_pixels = h1 - offset_y
        print(f"   📐 重叠计算: h1={h1}, offset_y={offset_y} → overlap={overlap_pixels}px")
        
        if overlap_pixels <= 0:
            print(f"   ❌ 负重叠: overlap_pixels={overlap_pixels}")
            return 0.0
        
        # 🔧 修正重复率计算：应该用较小的图作为基准
        min_height = min(h1, h2)
        overlap_ratio = overlap_pixels / min_height
        
        print(f"   📊 重复率: {overlap_pixels}/{min_height} = {overlap_ratio:.1%}")
        
        # 限制在0-1范围内
        return min(max(overlap_ratio, 0.0), 1.0)
        
    except Exception as e:
        print(f"   计算重复率失败: {e}")
        return 0.0


def _filter_duplicate_images(cv2_images: List[np.ndarray], 
                             high_threshold: float = 0.6,
                             low_threshold: float = 0.2,
                             identical_threshold: float = 0.95) -> List[np.ndarray]:
    """
    过滤重复的图片（改进版 - 支持完全重复检测，包括最后一张）
    
    规则：
      1. 标准跳过：如果图i与图i+1的重复率>60%，且图i与图i+2的重复率>20%，
         则跳过图i+1（认为图i+1是重复的中间帧）
      2. 完全重复跳过：如果图i与图i+1的重复率>95%（完全重复），则允许连续跳过
      3. 最后一张特殊处理：如果最后一张与倒数第二张完全重复（>95%），也会被跳过
      4. 不允许连续跳过2张图片（除非是完全重复）
      5. 过滤后至少保留2张图片（否则无法拼接）
    
    Args:
        cv2_images: OpenCV格式的图片列表
        high_threshold: 高重复率阈值（默认0.6，即60%）
        low_threshold: 低重复率阈值（默认0.2，即20%）
        identical_threshold: 完全重复阈值（默认0.95，即95%）
        
    Returns:
        过滤后的图片列表
    """
    if len(cv2_images) <= 2:
        return cv2_images
    
    print(f"\n🔍 检测重复图片 (阈值: 连续>{high_threshold*100:.0f}% 且隔一>{low_threshold*100:.0f}%, 完全重复>{identical_threshold*100:.0f}%)")
    
    filtered = []
    skip_indices = set()
    last_skipped = False  # 🆕 记录上一张是否被跳过
    
    i = 0
    while i < len(cv2_images):
        if i in skip_indices:
            i += 1
            continue
        
        # 检查是否需要跳过下一张图
        if i + 1 < len(cv2_images):
            # 计算 img[i] 和 img[i+1] 的重复率
            ratio_consecutive = _calculate_overlap_ratio(cv2_images[i], cv2_images[i+1])
            
            # 如果有 i+2，也计算它的重复率
            if i + 2 < len(cv2_images):
                ratio_skip_one = _calculate_overlap_ratio(cv2_images[i], cv2_images[i+2])
                print(f"   图{i+1}-图{i+2}: {ratio_consecutive*100:.1f}%, 图{i+1}-图{i+3}: {ratio_skip_one*100:.1f}%", end="")
            else:
                # 最后两张图，只能检测连续重复
                ratio_skip_one = 0.0
                print(f"   图{i+1}-图{i+2}: {ratio_consecutive*100:.1f}% (最后一张)", end="")
            
            # 🆕 检测是否为完全重复的图（一模一样）
            is_identical = ratio_consecutive > identical_threshold
            
            # 🆕 判断是否可以跳过
            if i + 2 < len(cv2_images):
                # 标准情况：需要同时满足连续>60% 且隔一>20%
                can_skip = (
                    ratio_consecutive > high_threshold and 
                    ratio_skip_one > low_threshold and
                    (not last_skipped or is_identical)  # 如果是完全重复，允许连续跳过
                )
            else:
                # 特殊情况：最后一张图，只需满足完全重复条件
                can_skip = is_identical and (not last_skipped or is_identical)
            
            # 🆕 检查跳过后是否至少还有2张图片
            potential_remaining = len(cv2_images) - len(skip_indices) - 1  # -1是因为要跳过当前的i+1
            if potential_remaining < 2:
                can_skip = False
                print(f" → ⚠️ 不能跳过（跳过后只剩{potential_remaining}张图片）", end="")
            
            # 判断是否满足跳过条件
            if can_skip:
                if is_identical:
                    print(f" → ❌ 跳过图{i+2}（完全重复）")
                else:
                    print(f" → ❌ 跳过图{i+2}（重复）")
                skip_indices.add(i + 1)
                filtered.append(cv2_images[i])
                last_skipped = True  # 🆕 标记已跳过
                i += 1
                continue
            else:
                if ratio_consecutive > high_threshold:
                    if i + 2 >= len(cv2_images):
                        # 最后一张，不满足完全重复条件
                        print(f" → ✅ 保留（最后一张，重复率{ratio_consecutive*100:.1f}%未达到完全重复阈值）")
                    elif ratio_skip_one <= low_threshold:
                        print(f" → ✅ 保留（隔一图重复率不足）")
                    elif last_skipped and not is_identical:
                        print(f" → ⚠️ 保留（不允许连续跳过）")
                    else:
                        print(f" → ✅ 保留")
                else:
                    print(f" → ✅ 保留")
                last_skipped = False  # 🆕 重置跳过标记
        else:
            last_skipped = False  # 🆕 重置跳过标记
        
        filtered.append(cv2_images[i])
        i += 1
    
    removed_count = len(cv2_images) - len(filtered)
    if removed_count > 0:
        print(f"✅ 过滤完成: 移除了 {removed_count} 张重复图片，保留 {len(filtered)} 张")
    else:
        print(f"✅ 未发现重复图片，保留全部 {len(filtered)} 张")
    
    return filtered


def smart_stitch_vertical(images: List[Union[Image.Image, np.ndarray]],
                         overlap_ratio: float = 0.3,
                         min_confidence: float = 0.5,
                         blend: bool = True,
                         strategy: str = 'pairwise',
                         filter_duplicates: bool = True,
                         duplicate_high_threshold: float = 0.6,
                         duplicate_low_threshold: float = 0.2,
                         duplicate_identical_threshold: float = 0.95,
                         scroll_distances: List[int] = None) -> Image.Image:
    """
    智能垂直拼接图片，使用特征点匹配自动识别重叠区域（支持滚动距离辅助）
    
    Args:
        images: 图片列表（PIL Image或numpy数组）
        overlap_ratio: 搜索范围比例（0.3表示在30%范围内搜索）
        min_confidence: 最小置信度，低于此值则降级处理
        blend: 是否在重叠区域进行alpha混合
        strategy: 拼接策略
            - 'pairwise' (推荐): 两两配对拼接，每次合成的图大小相近，匹配更准确
            - 'sequential': 顺序累积拼接，传统方式
        filter_duplicates: 是否过滤重复图片（默认True）
        duplicate_high_threshold: 连续两图的高重复率阈值（默认0.6，即60%）
        duplicate_low_threshold: 隔一图的低重复率阈值（默认0.2，即20%）
        duplicate_identical_threshold: 完全重复阈值（默认0.95，即95%，允许连续跳过）
        scroll_distances: 🆕 滚动距离列表（像素），用于初始估计，可选
        
    Returns:
        拼接后的PIL Image
    
    拼接策略说明:
        pairwise (两两配对):
            第1轮: [img1+img2, img3+img4, ...]  <- 小图+小图
            第2轮: [result1+result2, ...]        <- 中图+中图
            优势: 图片大小相近，特征点分布均衡，减少累积误差
        
        sequential (顺序累积):
            第1次: img1 + img2 = result1
            第2次: result1 + img3 = result2      <- 大图+小图
            第3次: result2 + img4 = result3      <- 更大图+小图
            缺点: 后期大小差异大，可能影响匹配精度
    """
    if not images:
        raise ValueError("图片列表不能为空")
    
    if len(images) == 1:
        if isinstance(images[0], np.ndarray):
            return cv2_to_pil(images[0])
        return images[0]
    
    print(f"\n{'='*60}")
    print(f"🎯 开始智能拼接: {len(images)} 张图片")
    print(f"   算法: ORB特征点匹配 + RANSAC")
    print(f"   策略: {strategy.upper()}")
    print(f"   参数: min_confidence={min_confidence}, blend={blend}")
    
    # 🆕 显示滚动距离信息
    if scroll_distances and len(scroll_distances) > 0:
        print(f"   🆕 滚动距离辅助: 启用 ({len(scroll_distances)} 个距离记录)")
        print(f"      总滚动距离: {sum(scroll_distances)}px, 平均: {sum(scroll_distances)/len(scroll_distances):.1f}px/次")
    else:
        print(f"   滚动距离辅助: 未启用 (纯图像匹配模式)")
    
    if filter_duplicates:
        print(f"   重复过滤: 启用 (连续>{duplicate_high_threshold*100:.0f}% 且隔一>{duplicate_low_threshold*100:.0f}%, 完全重复>{duplicate_identical_threshold*100:.0f}%)")
    print(f"{'='*60}")
    
    # 转换所有图片为OpenCV格式
    cv2_images = []
    for img in images:
        if isinstance(img, Image.Image):
            cv2_images.append(pil_to_cv2(img))
        else:
            cv2_images.append(img)
    
    # 确保所有图片宽度一致
    widths = [img.shape[1] for img in cv2_images]
    if len(set(widths)) > 1:
        print(f"⚠️ 图片宽度不一致: {set(widths)}，调整为最小宽度")
        min_width = min(widths)
        cv2_images = [img[:, :min_width] for img in cv2_images]
    
    # 过滤重复图片
    if filter_duplicates and len(cv2_images) > 2:
        cv2_images = _filter_duplicate_images(
            cv2_images, 
            high_threshold=duplicate_high_threshold,
            low_threshold=duplicate_low_threshold,
            identical_threshold=duplicate_identical_threshold
        )
        
        # 如果过滤后只剩一张图，直接返回
        if len(cv2_images) == 1:
            print(f"\n⚠️ 过滤后只剩1张图片，直接返回")
            return cv2_to_pil(cv2_images[0])
    
    # 根据策略选择拼接方式
    if strategy == 'pairwise':
        print(f"\n📊 使用两两配对拼接策略 (推荐)")
        print(f"   优势: 图片大小相近，匹配更准确，减少累积误差\n")
        result = _pairwise_stitch_recursive(
            cv2_images, 
            overlap_ratio, 
            min_confidence, 
            blend, 
            level=0,
            scroll_distances=scroll_distances  # 🆕 传递滚动距离
        )
        print(f"\n{'='*60}")
        print(f"✅ 两两配对拼接完成!")
        print(f"   最终尺寸: {result.shape[1]} x {result.shape[0]}")
        print(f"{'='*60}\n")
        
    else:  # sequential
        print(f"\n📊 使用顺序累积拼接策略 (传统方式)\n")
        result = _sequential_stitch(
            cv2_images,
            overlap_ratio,
            min_confidence,
            blend,
            scroll_distances  # 🆕 传递滚动距离
        )
    
    # 转换回PIL Image
    return cv2_to_pil(result)


def _sequential_stitch(cv2_images: List[np.ndarray],
                      overlap_ratio: float,
                      min_confidence: float,
                      blend: bool,
                      scroll_distances: List[int] = None) -> np.ndarray:
    """
    顺序累积拼接(原有逻辑)
    
    第1次: img1 + img2 = result1
    第2次: result1 + img3 = result2
    第3次: result2 + img4 = result3
    ...
    
    Args:
        cv2_images: OpenCV格式的图片列表
        overlap_ratio: 搜索范围比例
        min_confidence: 最小置信度
        blend: 是否启用羽化融合
        scroll_distances: 每次截图之间的滚动距离(像素)
    
    Returns:
        拼接后的图像(OpenCV格式)
    """
    result = cv2_images[0].copy()
    success_count = 0
    fallback_count = 0
    
    for i in range(1, len(cv2_images)):
        print(f"\n📎 拼接第 {i}/{len(cv2_images)-1} 对图片...")
        
        img2 = cv2_images[i]
        h1, w1 = result.shape[:2]
        h2, w2 = img2.shape[:2]
        
        # 🆕 获取当前截图的滚动距离
        scroll_distance = scroll_distances[i] if (scroll_distances and i < len(scroll_distances)) else None
        
        # 使用特征点匹配查找重叠
        offset_y, confidence = find_overlap_region(result, img2, overlap_ratio, scroll_distance=scroll_distance)
        
        # 判断是否使用智能拼接
        if offset_y is not None and confidence >= min_confidence:
            # 智能拼接成功
            success_count += 1
            
            overlap_pixels = h1 - offset_y
            
            # 验证合理性（改进版）
            if overlap_pixels <= 0:
                print(f"   ⚠️ 无重叠 ({overlap_pixels}px)，降级为简单拼接")
                fallback_count += 1
                result = _simple_append(result, img2)
                continue
            
            # 允许overlap >= h2的情况（小滚动）
            if overlap_pixels >= h2:
                # img2完全在重叠区域内，这是合理的小滚动
                print(f"   ℹ️ 小滚动场景: img2({h2}px)完全在重叠区域({overlap_pixels}px)内")
                # 继续执行智能拼接
            
            new_height = offset_y + h2
            
            # 修复: 使用 < 而不是 <=，允许 new_height == h1 的情况（完全重叠）
            if new_height < h1:
                print(f"   ⚠️ 新高度异常 ({new_height} < {h1})，降级为简单拼接")
                fallback_count += 1
                result = _simple_append(result, img2)
                continue
            
            # 执行智能拼接
            overlap_ratio_info = (overlap_pixels / h2 * 100) if h2 > 0 else 0
            print(f"   ✅ 使用智能拼接: overlap={overlap_pixels}px ({overlap_ratio_info:.1f}%), new_height={new_height}px")
            result = _blend_stitch(result, img2, offset_y, overlap_pixels, blend)
            
        else:
            # 降级为简单拼接
            conf_str = f"{confidence:.3f}" if confidence > 0 else "N/A"
            print(f"   ⚠️ 特征匹配失败 (confidence={conf_str})，使用简单拼接")
            fallback_count += 1
            result = _simple_append(result, img2)
    
    print(f"\n{'='*60}")
    print(f"✅ 顺序拼接完成!")
    print(f"   最终尺寸: {result.shape[1]} x {result.shape[0]}")
    print(f"   智能拼接: {success_count}/{len(cv2_images)-1}")
    print(f"   简单拼接: {fallback_count}/{len(cv2_images)-1}")
    print(f"{'='*60}\n")
    
    # 返回OpenCV图像（不是PIL）
    return result



def _blend_stitch(result: np.ndarray, img2: np.ndarray, 
                  offset_y: int, overlap_pixels: int, 
                  use_blend: bool) -> np.ndarray:
    """
    执行带混合的智能拼接（支持overlap>=h2的小滚动场景）
    
    Args:
        result: 当前结果图像
        img2: 要拼接的下一张图像
        offset_y: img2的起始Y坐标
        overlap_pixels: 重叠像素数（可能>=h2）
        use_blend: 是否使用alpha混合
    
    Returns:
        拼接后的图像
    """
    h1, w1 = result.shape[:2]
    h2, w2 = img2.shape[:2]
    new_height = offset_y + h2
    
    # 创建新画布
    if len(result.shape) == 3:
        new_result = np.zeros((new_height, w1, result.shape[2]), dtype=result.dtype)
    else:
        new_result = np.zeros((new_height, w1), dtype=result.dtype)
    
    # 复制result的非重叠部分
    new_result[:offset_y] = result[:offset_y]
    
    # 特殊情况：img2完全在重叠区域内（overlap_pixels >= h2）
    if overlap_pixels >= h2:
        print(f"      小滚动拼接: img2完全替换result的[{offset_y}:{offset_y+h2}]区域")
        
        if use_blend and h2 > 10:
            # 在img2的整个高度内进行混合
            blend_height = min(h2, 100)
            
            for y in range(blend_height):
                alpha = y / blend_height
                y_in_result = offset_y + y
                y_in_img2 = y
                
                if y_in_result < h1:
                    new_result[y_in_result] = (
                        result[y_in_result] * (1 - alpha) + 
                        img2[y_in_img2] * alpha
                    ).astype(result.dtype)
            
            # 剩余部分直接用img2
            if blend_height < h2:
                end_pos = min(offset_y + h2, h1)
                new_result[offset_y + blend_height:end_pos] = img2[blend_height:end_pos - offset_y]
        else:
            # 直接覆盖
            end_pos = min(offset_y + h2, h1)
            new_result[offset_y:end_pos] = img2[:end_pos - offset_y]
        
        # 如果img2超出了result的范围，复制超出部分
        if offset_y + h2 > h1:
            extra_start = h1 - offset_y
            new_result[h1:] = img2[extra_start:]
        
        return new_result
    
    # 正常情况：overlap_pixels < h2
    # 处理重叠区域
    if use_blend and overlap_pixels > 10:
        # Alpha混合（线性渐变）
        blend_height = min(overlap_pixels, 100)  # 最多混合100像素
        
        for y in range(blend_height):
            alpha = y / blend_height
            y_in_result = offset_y + y
            y_in_img2 = y
            
            if y_in_result < h1 and y_in_img2 < h2:
                new_result[y_in_result] = (
                    result[y_in_result] * (1 - alpha) + 
                    img2[y_in_img2] * alpha
                ).astype(result.dtype)
        
        # 重叠区域的剩余部分直接用img2
        if blend_height < overlap_pixels and overlap_pixels < h2:
            new_result[offset_y + blend_height:h1] = img2[blend_height:overlap_pixels]
    else:
        # 不混合，直接用img2覆盖重叠区域
        actual_overlap = min(overlap_pixels, h2)
        new_result[offset_y:offset_y + actual_overlap] = img2[:actual_overlap]
    
    # 复制img2的非重叠部分
    if h2 > overlap_pixels:
        new_result[h1:] = img2[overlap_pixels:]
    
    return new_result


def _simple_append(result: np.ndarray, img2: np.ndarray) -> np.ndarray:
    """
    简单垂直拼接（无重叠）
    
    Args:
        result: 当前结果图像
        img2: 要追加的图像
    
    Returns:
        拼接后的图像
    """
    h1, w1 = result.shape[:2]
    h2, w2 = img2.shape[:2]
    
    # 确保宽度一致
    min_width = min(w1, w2)
    result = result[:, :min_width]
    img2 = img2[:, :min_width]
    
    # 创建新画布
    if len(result.shape) == 3:
        new_result = np.zeros((h1 + h2, min_width, result.shape[2]), dtype=result.dtype)
    else:
        new_result = np.zeros((h1 + h2, min_width), dtype=result.dtype)
    
    new_result[:h1] = result
    new_result[h1:] = img2
    
    return new_result


def simple_stitch_fallback(images: List[Union[Image.Image, np.ndarray]]) -> Image.Image:
    """简单垂直拼接的后备方案（无重叠）"""
    print("📌 使用简单垂直拼接（无重叠）")
    
    from jietuba_stitch import stitch_images_vertical
    
    pil_images = []
    for img in images:
        if isinstance(img, np.ndarray):
            pil_images.append(cv2_to_pil(img))
        else:
            pil_images.append(img)
    
    return stitch_images_vertical(pil_images, align='left', spacing=0)


def auto_stitch(images: List[Union[Image.Image, np.ndarray, str, Path]],
               mode: str = 'smart',
               overlap_ratio: float = 0.3,
               min_confidence: float = 0.5,
               strategy: str = 'pairwise',
               filter_duplicates: bool = True,
               duplicate_high_threshold: float = 0.6,
               duplicate_low_threshold: float = 0.2,
               duplicate_identical_threshold: float = 0.95,
               scroll_distances: List[int] = None) -> Image.Image:
    """
    自动拼接图片（智能或简单模式）- 支持滚动距离辅助
    
    升级说明:
      - 🆕 支持滚动距离辅助（混合方案：物理坐标 + 图像匹配）
      - 现在使用ORB特征点匹配（之前是模板匹配）
      - 不再需要预估重叠比例（overlap_ratio仅用于搜索范围）
      - 置信度默认降低到0.5（特征匹配更可靠）
      - 新增两两配对拼接策略（默认）
      - 自动降级策略：特征匹配 → 简单拼接
      - 新增重复图片过滤功能（支持完全重复连续跳过）
    
    Args:
        images: 图片列表（可以是PIL Image、numpy数组或文件路径）
        mode: 'smart'（智能识别）或 'simple'（简单拼接）
        overlap_ratio: 搜索范围比例（0.3表示在图片30%范围内搜索特征点）
        min_confidence: 最小置信度阈值（0.5-0.7推荐）
        strategy: 拼接策略（仅在mode='smart'时有效）
            - 'pairwise' (推荐): 两两配对拼接，减少累积误差
            - 'sequential': 顺序累积拼接，传统方式
        filter_duplicates: 是否过滤重复图片（默认True）
        duplicate_high_threshold: 连续两图的高重复率阈值（默认0.6，即60%）
        duplicate_low_threshold: 隔一图的低重复率阈值（默认0.2，即20%）
        duplicate_identical_threshold: 完全重复阈值（默认0.95，即95%，允许连续跳过）
        scroll_distances: 🆕 滚动距离列表（像素），用于初始估计，可选
        
    Returns:
        拼接后的PIL Image
    """
    # 加载图片
    loaded_images = []
    for img in images:
        if isinstance(img, (str, Path)):
            loaded_images.append(Image.open(img))
        else:
            loaded_images.append(img)
    
    if not loaded_images:
        raise ValueError("没有可拼接的图片")
    
    if mode == 'smart':
        try:
            return smart_stitch_vertical(
                loaded_images, 
                overlap_ratio=overlap_ratio,
                min_confidence=min_confidence,
                blend=True,
                strategy=strategy,
                filter_duplicates=filter_duplicates,
                duplicate_high_threshold=duplicate_high_threshold,
                duplicate_low_threshold=duplicate_low_threshold,
                duplicate_identical_threshold=duplicate_identical_threshold,
                scroll_distances=scroll_distances  # 🆕 传递滚动距离
            )
        except Exception as e:
            print(f"⚠️ 智能拼接失败: {e}")
            print("   降级为简单拼接...")
            return simple_stitch_fallback(loaded_images)
    else:
        return simple_stitch_fallback(loaded_images)


if __name__ == "__main__":
    pass
