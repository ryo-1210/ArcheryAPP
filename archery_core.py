# =====================================================
# アーチェリー着弾点検出・統合ロジック(コアモジュール)
# Streamlitアプリとローカル/Colab検証の両方から呼び出される
# =====================================================

import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.optimize import linear_sum_assignment

# -----------------------------------------------------
# 設定
# -----------------------------------------------------
OUTPUT_SIZE = 1000      # 射影変換後の画像サイズ(px)
TARGET_SIZE_CM = 60     # 的紙の実寸(cm)
MAX_MATCH_DISTANCE = 8.0  # 左右マッチングの距離閾値(cm)
CONF_THRESHOLD = 0.3    # YOLO検出の信頼度閾値
IMG_SIZE = 1280         # YOLO推論時の画像サイズ

# 的のリング半径(cm)とスコア(World Archery 60cm的の目安。規格に応じて調整してください)
X_RING_RADIUS_CM = 1.525  # 10点リングの内側にあるインナーテン

RING_RADII_CM = [3.05, 6.1, 9.15, 12.2, 15.25, 18.3, 21.35, 24.4, 27.45, 30]
RING_COLORS = ['gold', 'gold', 'red', 'red', '#3498db', '#3498db', 'black', 'black', 'white', 'white']
RING_SCORES = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

# 矢の太径(cm)。得点判定時、矢が線に触れていれば内側(高得点側)を採用するために使う
ARROW_DIAMETER_CM = 0.8  # 実際に使用している矢の直径に合わせて調整してください


# -----------------------------------------------------
# 的紙の四隅検出
# -----------------------------------------------------
def detect_target_corners(img):
    """
    img: cv2で読み込んだ画像(BGR形式のndarray)
    戻り値: 四隅の座標(np.array, 4x2)
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_white = np.array([0, 0, 150])
    upper_white = np.array([180, 60, 255])
    mask = cv2.inRange(hsv, lower_white, upper_white)

    kernel = np.ones((15, 15), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("的紙の輪郭を検出できませんでした")

    largest = max(contours, key=cv2.contourArea)
    corners = get_corners_by_quadrant(largest, img.shape)
    return corners


def get_corners_by_quadrant(contour, img_shape):
    """輪郭点を画像の4象限に分け、各象限で最も外側の点を四隅とする"""
    h, w = img_shape[:2]
    points = contour.reshape(-1, 2)
    cx, cy = w / 2, h / 2

    corners = {}
    labels = ["top_left", "top_right", "bottom_left", "bottom_right"]

    for x, y in points:
        if x < cx and y < cy:
            key, score = "top_left", (cx - x) + (cy - y)
        elif x >= cx and y < cy:
            key, score = "top_right", (x - cx) + (cy - y)
        elif x < cx and y >= cy:
            key, score = "bottom_left", (cx - x) + (y - cy)
        else:
            key, score = "bottom_right", (x - cx) + (y - cy)

        if key not in corners or score > corners[key][2]:
            corners[key] = (x, y, score)

    if len(corners) < 4:
        raise ValueError("4隅すべてを検出できませんでした(的紙が画像端で切れている可能性があります)")

    ordered = [corners[k][:2] for k in labels]
    return np.array(ordered, dtype=np.float32)


# -----------------------------------------------------
# 射影変換
# -----------------------------------------------------
def get_perspective_matrix(corners, output_size=OUTPUT_SIZE):
    src_pts = np.array(corners, dtype=np.float32)
    dst_pts = np.array([
        [0, 0],
        [output_size, 0],
        [0, output_size],
        [output_size, output_size]
    ], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return matrix


def transform_points(points, matrix):
    if len(points) == 0:
        return np.array([])
    points = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(points, matrix)
    return transformed.reshape(-1, 2)


# -----------------------------------------------------
# YOLOでarrow_tip / target_centerを検出
# -----------------------------------------------------
def detect_arrows_and_center(model, img, conf_threshold=CONF_THRESHOLD, img_size=IMG_SIZE):
    """
    model: ultralytics YOLOモデル
    img: cv2で読み込んだ画像(BGR形式のndarray)
    """
    results = model(img, conf=conf_threshold, imgsz=img_size, verbose=False)
    boxes = results[0].boxes

    arrow_tip_points = []
    target_center_candidates = []  # (信頼度, 座標) のリスト

    for box in boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        x_center, y_center = box.xywh[0][:2].tolist()
        conf = float(box.conf[0])

        if cls_name == "arrow_tip":
            arrow_tip_points.append([x_center, y_center])
        elif cls_name == "target_center":
            target_center_candidates.append((conf, [x_center, y_center]))

    if len(target_center_candidates) == 0:
        raise ValueError("target_centerが検出されませんでした")

    # 信頼度が最も高いtarget_centerを採用
    target_center_candidates.sort(key=lambda x: x[0], reverse=True)
    target_center_point = target_center_candidates[0][1]
    num_centers_detected = len(target_center_candidates)

    return arrow_tip_points, target_center_point, num_centers_detected


# -----------------------------------------------------
# cm単位・中心原点の座標に正規化
# -----------------------------------------------------
def normalize_to_cm(points, center, output_size=OUTPUT_SIZE, target_size_cm=TARGET_SIZE_CM):
    if len(points) == 0:
        return np.array([])
    points = np.array(points)
    center = np.array(center)

    relative = points - center
    scale = target_size_cm / output_size
    cm_points = relative * scale
    cm_points[:, 1] *= -1  # Y軸反転(画像座標→グラフ座標)

    return cm_points


# -----------------------------------------------------
# 1枚の画像をまとめて処理(四隅検出→射影変換→検出→正規化)
# -----------------------------------------------------
def process_single_image(model, img, label=""):
    """
    img: cv2で読み込んだ画像(BGR形式のndarray)
    戻り値: (cm単位のarrow_tip座標リスト, ログ情報dict)
    """
    log = {"label": label}

    corners = detect_target_corners(img)
    matrix = get_perspective_matrix(corners)

    arrow_tip_raw, target_center_raw, num_centers = detect_arrows_and_center(model, img)
    log["num_arrows_detected"] = len(arrow_tip_raw)
    log["num_centers_detected"] = num_centers

    all_points = arrow_tip_raw + [target_center_raw]
    transformed = transform_points(all_points, matrix)

    transformed_tips = transformed[:-1]
    transformed_center = transformed[-1]

    cm_tips = normalize_to_cm(transformed_tips, transformed_center)

    return cm_tips, log


# -----------------------------------------------------
# 左右マッチング
# -----------------------------------------------------
def match_points(left_points, right_points, max_distance=MAX_MATCH_DISTANCE):
    left_points = np.array(left_points)
    right_points = np.array(right_points)

    n_left = len(left_points)
    n_right = len(right_points)

    if n_left == 0 or n_right == 0:
        return [], list(range(n_left)), list(range(n_right))

    cost_matrix = np.zeros((n_left, n_right))
    for i in range(n_left):
        for j in range(n_right):
            cost_matrix[i, j] = np.linalg.norm(left_points[i] - right_points[j])

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matched_pairs = []
    matched_left_idx = set()
    matched_right_idx = set()

    for i, j in zip(row_ind, col_ind):
        if cost_matrix[i, j] <= max_distance:
            matched_pairs.append((i, j, cost_matrix[i, j]))
            matched_left_idx.add(i)
            matched_right_idx.add(j)

    unmatched_left = [i for i in range(n_left) if i not in matched_left_idx]
    unmatched_right = [j for j in range(n_right) if j not in matched_right_idx]

    return matched_pairs, unmatched_left, unmatched_right


# -----------------------------------------------------
# 左右統合(中点 + 平均誤差補正)
# -----------------------------------------------------
def integrate_left_right(left_points, right_points, max_distance=MAX_MATCH_DISTANCE):
    matched_pairs, unmatched_left, unmatched_right = match_points(
        left_points, right_points, max_distance
    )

    left_points = np.array(left_points)
    right_points = np.array(right_points)

    true_points = []
    left_errors = []
    right_errors = []

    for i, j, dist in matched_pairs:
        true_point = (left_points[i] + right_points[j]) / 2
        true_points.append(true_point)
        left_errors.append(true_point - left_points[i])
        right_errors.append(true_point - right_points[j])

    avg_left_error = np.mean(left_errors, axis=0) if left_errors else np.array([0.0, 0.0])
    avg_right_error = np.mean(right_errors, axis=0) if right_errors else np.array([0.0, 0.0])

    log = {
        "matched_count": len(matched_pairs),
        "unmatched_left_count": len(unmatched_left),
        "unmatched_right_count": len(unmatched_right),
        "avg_left_error": avg_left_error,
        "avg_right_error": avg_right_error,
    }

    for i in unmatched_left:
        corrected = left_points[i] + avg_left_error
        true_points.append(corrected)

    for j in unmatched_right:
        corrected = right_points[j] + avg_right_error
        true_points.append(corrected)

    return np.array(true_points), log


# -----------------------------------------------------
# 得点計算
# -----------------------------------------------------
def calculate_score(point, ring_radii=RING_RADII_CM, scores=RING_SCORES,
                     x_ring_radius=X_RING_RADIUS_CM, arrow_diameter=ARROW_DIAMETER_CM):
    """
    着弾点の得点を計算する。
    矢の太さを考慮し、矢が線に触れていれば内側(高得点側)の点数を採用する。

    戻り値: (score, is_x) のタプル。is_xはXリングに入っているかどうか
    """
    distance = np.linalg.norm(point)
    arrow_radius = arrow_diameter / 2
    judged_distance = distance - arrow_radius

    is_x = judged_distance <= x_ring_radius

    for radius, score in zip(ring_radii, scores):
        if judged_distance <= radius:
            return score, is_x

    return 0, False  # 的の外


def format_score(score, is_x):
    """得点を表示用文字列にする(Xリングなら'X'、それ以外は点数表記)"""
    if is_x:
        return "X"
    return str(score)


# -----------------------------------------------------
# プロット描画(複数画面で共通利用)
# -----------------------------------------------------
def draw_target(ax, ring_radii=RING_RADII_CM, ring_colors=RING_COLORS, x_ring_radius=X_RING_RADIUS_CM):
    """的の同心円(Xリング含む)を描画する"""
    for r, c in zip(reversed(ring_radii), reversed(ring_colors)):
        circle = patches.Circle((0, 0), r, facecolor=c, edgecolor='gray', linewidth=0.5, zorder=1)
        ax.add_patch(circle)

    x_circle = patches.Circle((0, 0), x_ring_radius, facecolor='none',
                               edgecolor='black', linewidth=1.0, zorder=2)
    ax.add_patch(x_circle)


def plot_points(points, selected_idx=None, color='#27AE60', figsize=(6, 6),
                 arrow_diameter=ARROW_DIAMETER_CM, show_score_label=True):
    """
    着弾点群を的の上にプロットする(編集画面・データ閲覧画面の両方で使用)

    points: cm単位、的中心が原点のXY座標配列
    selected_idx: 選択中(強調表示)の矢のインデックス。Noneなら強調なし
    color: 矢の表示色
    show_score_label: 各矢の左上に番号ラベルを表示するか
    """
    fig, ax = plt.subplots(figsize=figsize)
    draw_target(ax)

    if len(points) > 0:
        points_arr = np.array(points)
        arrow_radius = arrow_diameter / 2

        scores_and_x = [calculate_score(p) for p in points_arr]
        total_score = sum(s for s, _ in scores_and_x)
        x_count = sum(1 for _, is_x in scores_and_x if is_x)

        for i, (x, y) in enumerate(points_arr):
            is_selected = (i == selected_idx)
            face_color = '#FF4136' if is_selected else color
            edge_color = 'yellow' if is_selected else 'white'
            edge_width = 2.5 if is_selected else 1.2

            arrow_circle = patches.Circle((x, y), arrow_radius, facecolor=face_color,
                                          edgecolor=edge_color, linewidth=edge_width, zorder=5, alpha=0.95)
            ax.add_patch(arrow_circle)

        info_text = f"合計点: {total_score} / 矢数: {len(points)} / X数: {x_count}"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes, va='top', fontsize=11,
               bbox=dict(facecolor='white', alpha=0.85))

        if show_score_label:
            for i, (x, y) in enumerate(points_arr):
                ax.annotate(str(i + 1), (x, y), textcoords="offset points", xytext=(8, 8),
                           fontsize=9, color='black', fontweight='bold',
                           bbox=dict(facecolor='white', alpha=0.75, pad=1))

    ax.set_xlim(-32, 32)
    ax.set_ylim(-32, 32)
    ax.set_aspect('equal')
    ax.set_xlabel('X (cm)')
    ax.set_ylabel('Y (cm)')
    ax.grid(True, alpha=0.3)
    return fig


# -----------------------------------------------------
# 統計計算(重心・散らばり・的中心との差分)
# -----------------------------------------------------
def calculate_statistics(points):
    """
    着弾点群から統計値を計算する。

    points: cm単位、的中心が原点のXY座標配列

    戻り値: dict
        centroid_x, centroid_y: 重心座標
        spread: 重心からの散らばり(標準偏差、全矢の重心までの距離のRMS)
        offset_x: 重心と的中心(0,0)とのX軸方向差分(+:右にズレ, -:左にズレ)
        offset_y: 重心と的中心(0,0)とのY軸方向差分(+:上にズレ, -:下にズレ)
    """
    if len(points) == 0:
        return {
            "centroid_x": None,
            "centroid_y": None,
            "spread": None,
            "offset_x": None,
            "offset_y": None,
        }

    points = np.array(points)
    centroid = points.mean(axis=0)
    centroid_x, centroid_y = centroid[0], centroid[1]

    # 重心からの散らばり(各矢と重心の距離のRMS)
    distances_from_centroid = np.linalg.norm(points - centroid, axis=1)
    spread = float(np.sqrt(np.mean(distances_from_centroid ** 2))) if len(points) > 0 else 0.0

    # 的中心(0,0)との差分。サイト調整用なので符号付きでそのまま使う
    offset_x = float(centroid_x)
    offset_y = float(centroid_y)

    return {
        "centroid_x": float(centroid_x),
        "centroid_y": float(centroid_y),
        "spread": spread,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }
