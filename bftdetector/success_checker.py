import glob, os
from .domdiff import DomDiff
from skimage.io import imread
from skimage.measure import shannon_entropy
from skimage.metrics import structural_similarity as ssim
import numpy as np
import pickle
from PIL import Image
from pathlib import Path

ddf = DomDiff()
MASK_COLOR = (0, 255, 0)
ERROR_HTML_SIZE_RATIO_MIN = 0.4
ERROR_IMG_ENTROPY_RATIO_MIN = 0.4
MODULE_PATH = str(Path(__file__).resolve().parent)


class SuccessChecker:
    def __init__(self, test_path):
        self.test_path = test_path
        self.model = None
        self.base_data = {}

        self.load_model()

        self.collect_base_data()

    def load_model(self):
        self.model = pickle.load(open(MODULE_PATH + '/brf_classifier.pkl', 'rb'))

    def get_common_pixels(self, filenames):
        imgs = []
        for filename in filenames:
            img = Image.open(filename)
            imgs.append(list(img.getdata()))

        img_common_pixel = imgs[0]
        for img in imgs[1:]:
            img_common_pixel = [img[i] if img[i] == img_common_pixel[i] else MASK_COLOR for i in range(len(img))]

        common_pixel_cnt = sum([0 if x == MASK_COLOR else 1 for x in img_common_pixel])
        return {'common_pixel': img_common_pixel, 'common_pixel_cnt': common_pixel_cnt}

    def collect_base_data(self):
        html_files_a = list(glob.glob(self.test_path + 'trace_a/*.html'))
        html_files_b = glob.glob(self.test_path + 'trace_b/*.html')
        html_files_b.sort(key=os.path.getmtime)
        html_files_b = list(html_files_b)
        html_file_ori = html_files_b[0]
        # img_file_ori = self.test_path + 'test_out/html/original.html'

        img_files_a = list(glob.glob(self.test_path + 'trace_a/*.jpg'))
        img_files_b = glob.glob(self.test_path + 'trace_b/*.jpg')
        img_files_b.sort(key=os.path.getmtime)
        img_files_b = list(img_files_b)
        img_file_ori = img_files_b[0]
        # img_file_ori = self.test_path + 'test_out/screenshot/original.jpg'

        # for DOM sim
        tags_a, tags_b, tags_comm = ddf.getDomDiffWithCommon(html_files_a, html_files_b + [html_file_ori]
                                                             , div_only=False)
        # for Img sim
        imgs_a = [imread(f, True) for f in img_files_a]
        imgs_b = [imread(f, True) for f in img_files_b]
        img_ori = imread(img_file_ori, True)

        imgs_common_a = self.get_common_pixels(img_files_a)
        imgs_common_b = self.get_common_pixels(img_files_b)

        # for Error checking
        # file sizes
        html_size_base = min([os.path.getsize(f) for f in html_files_a + html_files_b])
        # image entropy
        imgs_trace = [imread(f, True) for f in img_files_a + img_files_b]
        ent_trace = [shannon_entropy(img) for img in imgs_trace]
        ent_base = min(ent_trace)

        # self.base_data = {'inter_tags_b': tags_b, 'imgs_a': imgs_a, 'img_ori': img_ori
        #     , 'html_size_base': html_size_base, 'img_entropy_base': ent_base}

        self.base_data = {'inter_tags_a': tags_a, 'inter_tags_b': tags_b, 'img_ori': img_ori,
                          'imgs_a': imgs_a,
                          'imgs_common_a': imgs_common_a, 'imgs_common_b': imgs_common_b,
                          'html_size_base': html_size_base, 'img_entropy_base': ent_base}



    def is_error(self, html_file_out, img_file_out):
        if not os.path.exists(html_file_out) or not os.path.exists(img_file_out):
            return True

        html_ret_size = os.path.getsize(html_file_out)
        ent_ret = shannon_entropy(imread(img_file_out, True))

        html_size_ratio = html_ret_size / self.base_data['html_size_base']
        entropy_ratio = ent_ret / self.base_data['img_entropy_base']

        if html_size_ratio <= ERROR_HTML_SIZE_RATIO_MIN or entropy_ratio <= ERROR_IMG_ENTROPY_RATIO_MIN:
            return True

        return False


    def check_success(self, test_id):
        html_file_out = self.test_path + 'test_out/html/' + test_id + '.html'
        img_file_out = self.test_path + 'test_out/screenshot/' + test_id + '.jpg'

        if self.is_error(html_file_out, img_file_out):
            return 'Error'

        # DOM sim score
        tags_out = set(ddf.extract_tags_from_file(html_file_out, div_only=False))
        inter_a = self.base_data['inter_tags_a'] & tags_out
        if len(self.base_data['inter_tags_a']) == 0:
            score_domsim_a = 0
        else:
            score_domsim_a = len(inter_a) / len(self.base_data['inter_tags_a'])
        inter_b = self.base_data['inter_tags_b'] & tags_out
        if len(self.base_data['inter_tags_b']) == 0:
            score_domsim_not_b = 0
        else:
            score_domsim_not_b = 1 - len(inter_b) / len(self.base_data['inter_tags_b'])

        # img sim scores
        img_out = imread(img_file_out, True)

        # img common scores
        cp_a = self.base_data['imgs_common_a']['common_pixel']
        cp_b = self.base_data['imgs_common_b']['common_pixel']
        cp_a_cnt = self.base_data['imgs_common_a']['common_pixel_cnt']
        cp_b_cnt = self.base_data['imgs_common_b']['common_pixel_cnt']

        if cp_a_cnt == 0 and cp_b_cnt:
            # no common pixels
            score_imgcomsim_a = np.mean([ssim(img, img_out, multichannel=False) for img in self.base_data['imgs_a']])
            score_imgcomsim_b = np.mean([ssim(img, img_out, multichannel=False) for img in self.base_data['imgs_b']])

        else:
            img_size = len(cp_a)
            img = Image.open(img_file_out)
            imgdata = img.getdata()
            if cp_a_cnt != 0:
                score_imgcomsim_a = sum(
                    [1 if cp_a[i] != MASK_COLOR and imgdata[i] == cp_a[i] else 0 for i in range(img_size)]) / cp_a_cnt
            if cp_b_cnt != 0:
                score_imgcomsim_b = 1 - sum(
                    [1 if cp_b[i] != MASK_COLOR and imgdata[i] == cp_b[i] else 0 for i in range(img_size)]) / cp_b_cnt


        score_imgsim_a = np.mean([ssim(img, img_out, multichannel=False) for img in self.base_data['imgs_a']])
        sim_ori = ssim(img_out, self.base_data['img_ori'], multichannel=False)
        score_imgsim_not_ori = 1 - sim_ori

        #test_data = np.array([score_domsim_a, score_domsim_not_b, score_imgcomsim_a, score_imgcomsim_b, score_imgsim_not_ori])
        test_data = np.array(
            [score_domsim_not_b, score_imgsim_a, score_imgsim_not_ori])
        test_data = test_data.reshape(1, -1)
        pred = self.model.predict(test_data)[0]

        final_score = -4.07 + score_domsim_not_b * 1.45 + score_imgsim_a * 2.96 + score_imgsim_not_ori * 5.92
        # print(pred, final_score)

        if pred != 0 and final_score > 0:
            return 'Success'
        else:
            return 'Failed'

