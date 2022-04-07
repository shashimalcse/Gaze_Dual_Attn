import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import torchvision.transforms.functional as TF
from torch.autograd import Variable
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import DataParallel
# from models.gazenet import GazeNet

import time
import os
import numpy as np
import json
import cv2
from PIL import Image, ImageOps
import random
from tqdm import tqdm
import operator
import itertools
from scipy.io import  loadmat
import logging

from scipy import signal
import matplotlib.pyplot as plt
from utils import get_paste_kernel, kernel_map


import pickle
from skimage import io
from dataloader import chong_imutils

def _get_transform(input_resolution):
    transform_list = []
    transform_list.append(transforms.Resize((input_resolution, input_resolution)))
    transform_list.append(transforms.ToTensor())
    transform_list.append(transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]))
    return transforms.Compose(transform_list)

class RetailGaze(Dataset):
        def __init__(self, root_dir, mat_file, training='train', include_path=False, input_size=224, output_size=64, imshow = False, use_gtbox=False):
            assert (training in set(['train', 'test']))
            self.root_dir = root_dir
            self.mat_file = mat_file
            self.training = training
            self.include_path = include_path
            self.input_size = input_size
            self.output_size = output_size
            self.imshow = imshow
            self.transform = _get_transform(input_size)
            self.use_gtbox= use_gtbox

            with open(mat_file, 'rb') as f:
                self.data = pickle.load(f)
                self.image_num = len(self.data)

            print("Number of Images:", self.image_num)
            # logging.info('%s contains %d images' % (self.mat_file, self.image_num))

        def __len__(self):
            return self.image_num

        def __getitem__(self, idx):
            gaze_inside = True
            data = self.data[idx]
            image_path = data['filename']
            image_path = os.path.join(self.root_dir, image_path)

            gaze = [float(data['gaze_cx'])/640, float(data['gaze_cy'])/480]
            # eyess = np.array([eye[0],eye[1]]).astype(np.float)
            gaze_x, gaze_y = gaze

            image_path = image_path.replace('\\', '/')
            img = Image.open(image_path)
            img = img.convert('RGB')
            width, height = img.size
            #Get bounding boxes and class labels as well as gt index for gazed object
            gt_bboxes, gt_labels = np.zeros(1), np.zeros(1)
            gt_labels = np.expand_dims(gt_labels, axis=0)
            width, height = img.size
            hbox = np.copy(data['ann']['hbox'])
            x_min, y_min, x_max, y_max = hbox
            head_x=((x_min+x_max)/2)/640
            head_y=((y_min+y_max)/2)/480
            eye = np.array([head_x, head_y])
            eye_x, eye_y = eye
            k = 0.1
            x_min = (eye_x - 0.15) * width
            y_min = (eye_y - 0.15) * height
            x_max = (eye_x + 0.15) * width
            y_max = (eye_y + 0.15) * height
            if x_min < 0:
                x_min = 0
            if y_min < 0:
                y_min = 0
            if x_max < 0:
                x_max = 0
            if y_max < 0:
                y_max = 0
            x_min -= k * abs(x_max - x_min)
            y_min -= k * abs(y_max - y_min)
            x_max += k * abs(x_max - x_min)
            y_max += k * abs(y_max - y_min)
            x_min, y_min, x_max, y_max = map(float, [x_min, y_min, x_max, y_max])
            if self.use_gtbox:
                gt_bboxes = np.copy(data['ann']['bboxes']) / [640, 480, 640, 480]
                gt_labels = np.copy(data['ann']['labels'])
                # gtbox = gt_bboxes[gaze_idx]
            face = img.crop((int(x_min), int(y_min), int(x_max), int(y_max)))
            head_x=((x_min+x_max)/2)/640
            head_y=((y_min+y_max)/2)/480
            head = np.array([head_x, head_y])

            gt_label = np.array([gaze_x, gaze_y])
            head_box = np.array([x_min/640, y_min/480, x_max/640, y_max/480])

            if self.imshow:
                img.save("img_aug.jpg")

            if self.transform is not None:
                img = self.transform(img)
                face = self.transform(face)

            if self.training == 'test':
                return img, face, head, gt_label, head_box, image_path
            elif self.training == 'test_prediction':
                pass
            else:
                return img, face, head, gt_label, head_box, image_path