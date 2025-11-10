import cv2
import numpy as np
import glob

class CameraCalibrator():
    def __init__(self, w, h, square_size, images_path, model: str = 'fisheye'):
        self.w = w
        self.h = h
        self.square_size = square_size  # 棋盘格每个方格的尺寸，单位mm
        self.objpoints = []
        self.imgpoints = []
        self.images_path = images_path  # './data/one_calibration_image/*.jpg'
        self.model = model.lower() if isinstance(model, str) else 'fisheye'

    def run_calibration(self, images_path, w, h, square_size):
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        objp = np.zeros((w * h, 3), np.float32)
        objp[:, :2] = np.mgrid[0:w, 0:h].T.reshape(-1, 2)
        objp = objp * square_size

        images = glob.glob(images_path)
        i = 0
        processed_images = []
        for fname in images:
            img = cv2.imread(fname)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            u, v = img.shape[:2]
            ret, corners = cv2.findChessboardCorners(gray, (w, h), None)
            if ret:
                i += 1
                # 在原角点的基础上寻找亚像素角点
                cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                # 追加进入世界三维点和平面二维点中
                self.objpoints.append(objp)
                self.imgpoints.append(corners)
                # 将角点在图像上显示
                cv2.drawChessboardCorners(img, (w, h), corners, ret)
        cv2.destroyAllWindows()

        # 标定（支持 pinhole 与 fisheye）
        if self.model == 'fisheye':
            # OpenCV fisheye 需要 (N,1,3) 与 (N,1,2) 的float64格式
            objpoints_fe = [op.reshape(-1, 1, 3).astype(np.float64) for op in self.objpoints]
            imgpoints_fe = [ip.reshape(-1, 1, 2).astype(np.float64) for ip in self.imgpoints]
            K = np.zeros((3, 3))
            D = np.zeros((4, 1))  # 鱼眼畸变通常是4个参数 k1, k2, k3, k4
            flags = (
                cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC
                | cv2.fisheye.CALIB_CHECK_COND
                | cv2.fisheye.CALIB_FIX_SKEW
            )
            rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
                objectPoints=objpoints_fe,
                imagePoints=imgpoints_fe,
                image_size=gray.shape[::-1],
                K=K,
                D=D,
                rvecs=None,
                tvecs=None,
                flags=flags,
                criteria=criteria,
            )
            # 估计去畸变新内参
            newcameramtx = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K, D, gray.shape[::-1], np.eye(3), balance=0.0
            )
            return rms, K, D, u, v, processed_images, rvecs, tvecs, newcameramtx
        else:
            # pinhole
            ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                self.objpoints, self.imgpoints, gray.shape[::-1], None, None
            )
            newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (u, v), 0, (u, v))
            return ret, mtx, dist, u, v, processed_images, rvecs, tvecs, newcameramtx

    def start_capture(self, mtx, dist, u, v):
        camera = cv2.VideoCapture(0)
        
        # 设置窗口位置
        cv2.namedWindow('原始图像', cv2.WINDOW_NORMAL)
        cv2.namedWindow('去畸变后图像', cv2.WINDOW_NORMAL)
        cv2.moveWindow('原始图像', 100, 100)
        cv2.moveWindow('去畸变后图像', 750, 100)
        
        print(f"📷 开始相机预览 - 模型: {self.model}")
        print("按 'q' 退出预览")
        
        while True:
            (grabbed, frame) = camera.read()
            if not grabbed:
                break
            
            h1, w1 = frame.shape[:2]
            
            # 显示原始图像
            cv2.imshow('原始图像', frame)
            
            # 根据模型选择去畸变方法
            if self.model == 'fisheye' and dist is not None and len(dist) >= 4:
                print(f"🐟 使用鱼眼模型去畸变") if not hasattr(self, '_printed_model') else None
                R = np.eye(3)
                # 方案A：使用原始内参矩阵作为新内参，确保与手眼标定一致
                newcameramtx = mtx.copy()  # 直接使用原始内参K
                mapx, mapy = cv2.fisheye.initUndistortRectifyMap(
                    mtx, dist, R, newcameramtx, (w1, h1), cv2.CV_16SC2
                )
                dst2 = cv2.remap(
                    frame, mapx, mapy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
                )
                
                # 在图像上添加文字标识
                cv2.putText(dst2, f"Fisheye Undistorted (Original K)", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                print(f"📐 使用针孔模型去畸变") if not hasattr(self, '_printed_model') else None
                # 方案A：使用原始内参矩阵
                newcameramtx = mtx.copy()  # 直接使用原始内参K
                mapx, mapy = cv2.initUndistortRectifyMap(
                    mtx, dist, None, newcameramtx, (w1, h1), cv2.CV_16SC2
                )
                dst2 = cv2.remap(frame, mapx, mapy, cv2.INTER_LINEAR)
                
                # 在图像上添加文字标识
                cv2.putText(dst2, f"Pinhole Undistorted (Original K)", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # 在原始图像上添加文字标识
            cv2.putText(frame, "Original Image", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # 显示去畸变后的图像
            cv2.imshow('去畸变后图像', dst2)
            
            # 标记已打印模型信息
            self._printed_model = True
            
            # 按q退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        camera.release()
        cv2.destroyAllWindows()
        print("✅ 相机预览已关闭")


if __name__ == "__main__":
    CC = CameraCalibrator(8, 5, 30, 'F:/Desktop/Horizon_Arm/data/one_calibration_image/*.jpg')
    ret, mtx, dist, u, v, processed_images, rvecs, tvecs, newcameramtx = CC.run_calibration(
        CC.images_path, CC.w, CC.h, CC.square_size
    )
    CC.start_capture(mtx, dist, u, v)

    