"""Stitch the evacuation-plan photos into one reference image per floor.

Run: python3 scripts/stitch_evacuation_plans.py
Needs opencv-python-headless and numpy (scripts/requirements-map.txt).

Each floor was photographed as two or three overlapping sheets. Photos are warped
into one frame: the floor-1 middle sheet defines it; other sheets are matched to
it with SIFT features, and sheets that share too little with it (the north
halves and the floor-3 middle sheet) are fitted on the corners of the classroom
wings, assuming the blocks are evenly spaced. The result is turned 180 degrees to the app's orientation
(Block H at the top) and written in map units, so scripts/campus_layout.py
coordinates can be read straight off the image.
"""
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / 'docs/map-source/evacuation-plans'
SCALE = 1.5                     # output pixels per map unit
WIDTH, HEIGHT, DY = 800, 1660, 20
# Crop offset of each saved photo inside the original picture.
OFFSET = {'floor-1-south': (140, 40), 'floor-1-middle': (150, 60), 'floor-1-north': (170, 120),
          'floor-2-south': (200, 80), 'floor-2-middle': (290, 120), 'floor-2-north': (190, 110),
          'floor-3-south': (180, 70), 'floor-3-middle': (60, 250), 'floor-3-north': (170, 40)}


def wing(block_index):
    """Corners of a block's classroom wing in the frame of the floor-1 middle photo."""
    top = 327.5 + 216.5 * block_index
    return [(438.5, top), (591, top), (591, top + 46), (438.5, top + 46)]


def corners(tl, tr, bottom):
    return [tl, tr, (tr[0], bottom), (tl[0], bottom)]


# Wing corners read from sheets that share no detail with floor 1 (original photo pixels):
# Blocks D and E on the floor-3 middle sheet, Blocks F, G and H on the north sheets.
MIDDLE = {'floor-3-middle': corners((346, 511.3), (492.5, 511.3), 559) + corners((346, 730), (494.6, 730), 779.2)}
NORTH = {
    'floor-1-north': corners((437, 176), (571, 176), 218) + corners((432, 372), (566, 372), 414) + corners((425, 570), (562, 570), 611),
    'floor-2-north': corners((425, 106.7), (558, 106.7), 150) + corners((422.5, 297.5), (557.5, 297.5), 345) + corners((420, 497.5), (557.5, 497.5), 542.5),
    'floor-3-north': corners((411, 114), (545, 114), 160) + corners((409, 303.5), (542.5, 303.5), 350) + corners((402.5, 502.5), (540, 502.5), 549),
}


def image(name):
    return cv2.imread(str(PLANS / f'{name}.jpg'))


def to_frame_from_original(name):
    """Matrix taking a saved (cropped) photo's pixels back to its original pixels."""
    x, y = OFFSET[name]
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], float)


def match(a, b):
    """Homography from photo a to photo b, both in original pixels."""
    sift = cv2.SIFT_create(10000)
    ka, da = sift.detectAndCompute(cv2.cvtColor(image(a), cv2.COLOR_BGR2GRAY), None)
    kb, db = sift.detectAndCompute(cv2.cvtColor(image(b), cv2.COLOR_BGR2GRAY), None)
    good = [m for m, n in cv2.BFMatcher().knnMatch(da, db, k=2) if m.distance < 0.78 * n.distance]
    pa = np.float32([ka[m.queryIdx].pt for m in good])
    pb = np.float32([kb[m.trainIdx].pt for m in good])
    homography, inliers = cv2.findHomography(pa, pb, cv2.RANSAC, 4.0)
    print(f'{a} -> {b}: {int(inliers.sum())} of {len(good)} matches agree')
    return to_frame_from_original(b) @ homography @ np.linalg.inv(to_frame_from_original(a))


def fit_wings(points, blocks):
    source = np.float32(points)
    target = np.float32([p for k in blocks for p in wing(k)])
    affine, _ = cv2.estimateAffine2D(source, target)
    return np.vstack([affine, [0, 0, 1]])


def main():
    frame = {'floor-1-middle': np.eye(3)}
    frame['floor-1-south'] = match('floor-1-south', 'floor-1-middle')
    frame['floor-2-south'] = frame['floor-1-south'] @ match('floor-2-south', 'floor-1-south')
    frame['floor-2-middle'] = frame['floor-2-south'] @ match('floor-2-middle', 'floor-2-south')
    frame['floor-3-middle'] = fit_wings(MIDDLE['floor-3-middle'], (0, 1))
    frame['floor-3-south'] = frame['floor-3-middle'] @ match('floor-3-south', 'floor-3-middle')
    for name, points in NORTH.items():
        frame[name] = fit_wings(points, (2, 3, 4))
    # Frame -> map units (turned 180 degrees), then -> output pixels.
    to_map = np.array([[-1.2, 0, 810 * 1.2], [0, -1.2, 1320 * 1.2 + DY], [0, 0, 1]], float)
    to_pixels = np.diag([SCALE, SCALE, 1.0])
    size = (int(WIDTH * SCALE), int(HEIGHT * SCALE))
    order = {1: ['floor-1-north', 'floor-1-middle', 'floor-1-south'],
             2: ['floor-2-north', 'floor-2-middle', 'floor-2-south'],
             3: ['floor-3-north', 'floor-3-middle', 'floor-3-south']}
    for floor, names in order.items():
        canvas = np.full((size[1], size[0], 3), 255, np.uint8)
        for name in names:  # later sheets are drawn on top
            photo = image(name)
            matrix = to_pixels @ to_map @ frame[name] @ to_frame_from_original(name)
            warped = cv2.warpPerspective(photo, matrix, size)
            mask = cv2.warpPerspective(np.full(photo.shape[:2], 255, np.uint8), matrix, size)
            canvas[mask > 0] = warped[mask > 0]
        out = PLANS / f'floor-{floor}-stitched.jpg'
        cv2.imwrite(str(out), canvas, [cv2.IMWRITE_JPEG_QUALITY, 82])
        print('wrote', out.relative_to(ROOT))


if __name__ == '__main__':
    main()
