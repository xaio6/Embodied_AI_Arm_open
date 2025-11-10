import cv2
import os
import numpy as np

class Two_Camera_Clibration():
    def __init__(self, w, h, square_size, leftpath, rightpath, model: str = 'fisheye'):
        self.leftpath = leftpath  # r'data\two_calibration_image\left'
        self.rightpath = rightpath  # r'data\two_calibration_image\right'
        self.w = w
        self.h = h
        self.square_size = square_size
        self.imgpoints_l = []  # 存放左图像坐标系下角点位置
        self.imgpoints_r = []  # 存放右图像坐标系下角点位置
        self.objpoints = []  # 存放世界坐标系下角点位置
        self.model = model.lower() if isinstance(model, str) else 'fisheye'

    def calibration_run(self, w, h, square_size):
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        objp = np.zeros((1, w * h, 3), np.float32)
        objp[0, :, :2] = np.mgrid[0:w, 0:h].T.reshape(-1, 2)
        objp[0, :, 0] *= square_size
        objp[0, :, 1] *= square_size

        for ii in os.listdir(self.leftpath):
            img_l = cv2.imread(os.path.join(self.leftpath, ii))
            if img_l is None:
                continue
            gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
            img_r = cv2.imread(os.path.join(self.rightpath, ii))
            if img_r is None:
                continue
            gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
            ret_l, corners_l = cv2.findChessboardCorners(gray_l, (w, h), None)  # 检测棋盘格内角点
            ret_r, corners_r = cv2.findChessboardCorners(gray_r, (w, h), None)
            if ret_l and ret_r:
                self.objpoints.append(objp)
                corners2_l = cv2.cornerSubPix(gray_l, corners_l, (11, 11), (-1, -1), criteria)
                self.imgpoints_l.append(corners2_l)
                corners2_r = cv2.cornerSubPix(gray_r, corners_r, (11, 11), (-1, -1), criteria)
                self.imgpoints_r.append(corners2_r)

        if self.model == 'fisheye':
            # 单目标定（鱼眼）
            obj_l = [o.reshape(-1, 1, 3).astype(np.float64) for o in self.objpoints]
            obj_r = obj_l  # 相同棋盘三维点
            img_l = [ip.reshape(-1, 1, 2).astype(np.float64) for ip in self.imgpoints_l]
            img_r = [ip.reshape(-1, 1, 2).astype(np.float64) for ip in self.imgpoints_r]
            K1 = np.zeros((3, 3))
            D1 = np.zeros((4, 1))
            K2 = np.zeros((3, 3))
            D2 = np.zeros((4, 1))
            flags = (
                cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC
                | cv2.fisheye.CALIB_CHECK_COND
                | cv2.fisheye.CALIB_FIX_SKEW
            )
            
            print(f"开始鱼眼单目标定...")
            rms1, K1, D1, rvecs_l, tvecs_l = cv2.fisheye.calibrate(
                obj_l, img_l, gray_l.shape[::-1], K1, D1, None, None, flags=flags, criteria=criteria
            )
            rms2, K2, D2, rvecs_r, tvecs_r = cv2.fisheye.calibrate(
                obj_r, img_r, gray_r.shape[::-1], K2, D2, None, None, flags=flags, criteria=criteria
            )
            
            print(f"左相机标定完成，RMS: {rms1:.4f}")
            print(f"右相机标定完成，RMS: {rms2:.4f}")
            
            # 准备鱼眼双目标定
            R = np.eye(3)
            T = np.zeros((3, 1))
            flags_st = cv2.fisheye.CALIB_FIX_INTRINSIC
            
            print(f"开始鱼眼双目标定...")
            
            # 直接调用并捕获所有返回值
            stereo_result = cv2.fisheye.stereoCalibrate(
                objectPoints=obj_l,
                imagePoints1=img_l,
                imagePoints2=img_r,
                K1=K1,
                D1=D1,
                K2=K2,
                D2=D2,
                imageSize=gray_l.shape[::-1],
                R=R,
                T=T,
                flags=flags_st,
                criteria=criteria,
            )

            # 鱼眼双目标定实际返回9个值：rms, K1, D1, K2, D2, R, T, rvecs, tvecs
            rms_st, K1_out, D1_out, K2_out, D2_out, R_out, T_out, rvecs_st, tvecs_st = stereo_result
            return K1_out, D1_out, K2_out, D2_out, R_out, T_out

                
        else:
            # 先分别做单目标定
            ret, mtx_l, dist_l, rvecs_l, tvecs_l = cv2.calibrateCamera(
                self.objpoints, self.imgpoints_l, gray_l.shape[::-1], None, None
            )
            ret, mtx_r, dist_r, rvecs_r, tvecs_r = cv2.calibrateCamera(
                self.objpoints, self.imgpoints_r, gray_r.shape[::-1], None, None
            )

            # cv2.stereoCalibrate 返回9个值：retval, cameraMatrix1, dist1, cameraMatrix2, dist2, R, T, E, F
            retval, cameraMatrix1, dist1, cameraMatrix2, dist2, R, T, E, F = cv2.stereoCalibrate(
                self.objpoints,
                self.imgpoints_l,
                self.imgpoints_r,
                mtx_l,
                dist_l,
                mtx_r,
                dist_r,
                gray_l.shape[::-1],
            )  # 再做双目标定

            print(f"针孔双目标定完成，RMS误差: {retval:.4f}")
            print(f"基础矩阵F:\n{F}")
            
            # 返回6个值，与鱼眼模型保持一致
            return cameraMatrix1, dist1, cameraMatrix2, dist2, R, T

if __name__ == "__main__":
    TCC = Two_Camera_Clibration(10, 7, 22, r'data\\two_calibration_image\\left', r'data\\two_calibration_image\\right')
    TCC.calibration_run(TCC.w, TCC.h, TCC.square_size)