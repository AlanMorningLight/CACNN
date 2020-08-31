import pathlib,random
import scipy.io as sio
import numpy as np
from sklearn.decomposition import PCA
import tensorflow as tf
import unit,os

class Data():

    def __init__(self,args):
        self.data_path = args.data_path
        self.train_num = args.train_num
        self.seed = args.seed
        self.data_name = args.data_name
        self.result = args.result
        self.tfrecords = args.tfrecords
        self.args = args
        self.value = args.threshold
        self.cube_length = args.cube_size * 2 + 1
        self.n_components=args.n_components
        self.cube_size = args.cube_size
        self.padding = args.padding
        if self.data_name == 'PaviaU' or self.data_name == 'Indian_pines' or self.data_name == 'Houston':
            self.data_dict = sio.loadmat(str(pathlib.Path(self.data_path, self.data_name + '.mat')))
        elif self.data_name == 'Salinas':
            self.data_dict = sio.loadmat(str(pathlib.Path(self.data_path, self.data_name + '_corrected.mat')))
        self.data_gt_dict = sio.loadmat(str(pathlib.Path(self.data_path, self.data_name+'_gt.mat')))
        data_name = [t for t in list(self.data_dict.keys()) if not t.startswith('__')][0]
        data_gt_name = [t for t in list(self.data_gt_dict.keys()) if not t.startswith('__')][0]
        self.data = self.data_dict[data_name]
        self.data = unit.max_min(self.data).astype(np.float32)
        shape0 = self.data.shape[0]
        shape1 = self.data.shape[1]
        data = np.reshape(self.data, [shape0 * shape1, -1])
        n_components = self.n_components
        pca = PCA(n_components=n_components, svd_solver="full")#PCA algorithm
        data = pca.fit(data).transform(data)
        self.data = np.reshape(data, [shape0, shape1, -1])
        self.data = np.lib.pad(self.data, ((self.padding, self.padding), (self.padding, self.padding), (0, 0)), 'symmetric')
        #print(self.data.shape)
        self.data_gt = self.data_gt_dict[data_gt_name].astype(np.int64)
        #print(self.data_gt.shape)
        self.dim = self.data.shape[2]

    def neighbor_add(self,row, col, labels, w_size=4,flag=True):  # 给出 row，col和标签，返回w_size大小的cube，flag=True表示为训练样本
        '''
        :param row: Label location(row)
        :param col: Label location(col)
        :param labels: labels
        :param w_size: the size of patch
        :param flag: flag
        :return: return patch
        '''
        t = w_size // 2
        #width = t
        cube = np.zeros(shape=[w_size, w_size, self.data.shape[2]])
        labels += 1
        for i in range(-t, t+1):
            for j in range(-t, t+1):
                if i + row < 0 or i + row > self.data.shape[0] or j + col < 0 or j + col > self.data.shape[1]:
                    if flag == True:
                        s = random.sample(self.train_pos[labels], 1)
                        cube[i + t, j + t] = s[0][1]
                    else:
                        s = random.sample(self.test_pos[labels], 1)
                        cube[i + t, j + t] = s[0][1]
                else:
                    cube[i + t, j + t] = self.data[i + row, j + col]
        return cube

    def read_data(self):
        data = self.data
        data_gt = self.data_gt
        if self.data_name == 'Indian_pines': # We selected the most 9 types of tags in Indian_pines  dataset
            imGIS = data_gt
            origin_num = np.zeros(shape=[17], dtype=int)
            for i in range(imGIS.shape[0]):
                for j in range(imGIS.shape[1]):
                    for k in range(1, 17):
                        if imGIS[i][j] == k:
                            origin_num[k] += 1
            index = 0
            data_num = np.zeros(shape=[9], dtype=int)  # per calsses's num
            data_label = np.zeros(shape=[9], dtype=int)  # original labels
            for i in range(len(origin_num)):
                if origin_num[i] > 400:
                    data_num[index] = origin_num[i]
                    data_label[index] = i
                    index += 1
            iG = np.zeros([imGIS.shape[0], imGIS.shape[1]], dtype=imGIS.dtype)
            for i in range(imGIS.shape[0]):
                for j in range(imGIS.shape[1]):
                    if imGIS[i, j] in data_label:
                        for k in range(len(data_label)):
                            if imGIS[i][j] == data_label[k]:
                                iG[i, j] = k + 1
                                continue
            imGIS = iG

            data_gt = imGIS
            self.data_gt = data_gt
        #store the shape of data, data, label...
        sio.savemat(os.path.join(self.result,'info.mat'),{
            'shape':self.data.shape,
            'data':self.data,
            'data_gt':self.data_gt,
            'dim':self.data.shape[2],
            'class_num':np.max(self.data_gt)
        })

        class_num = np.max(data_gt)
        data_pos = {i: [] for i in range(1, class_num + 1)}
        for i in range(data_gt.shape[0]):
            for j in range(data_gt.shape[1]):
                for k in range(1, class_num + 1):
                    if data_gt[i, j] == k:
                        #data_pos[k].append([i, j])
                        data_pos[k].append([i+self.padding, j+self.padding])
        self.data_pos = data_pos

        if self.args.fix_seed:
            random.seed(self.seed)
        train_pos = dict()
        test_pos = dict()
        for k, v in data_pos.items(): # Training set number of tags
            if self.train_num > 0 and self.train_num < 1:
                train_num = self.train_num * len(v)
            else:
                train_num = self.train_num
            train_pos[k] = random.sample(v, int(train_num))
            test_pos[k] = [i for i in v if i not in train_pos[k]]
        self.train_pos = train_pos
        self.test_pos = test_pos
        train_pos_all = list()
        test_pos_all = list()
        # The location of the  pixel and the corresponding label value
        for k,v in train_pos.items():
            for t in v:
                train_pos_all.append([k,t])
        for k,v in test_pos.items():
            for t in v:
                test_pos_all.append([k,t])

        def _int64_feature(value):
            return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

        def _bytes_feature(value):
            return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

        # train data
        train_data_name = os.path.join(self.tfrecords, 'train_data.tfrecords')
        writer = tf.python_io.TFRecordWriter(train_data_name)
        for i in train_pos_all:
            [r,c] = i[1]
            pixel_t = self.neighbor_add(r,c,i[0]-1,w_size=self.cube_size).astype(np.float32).tostring()
            label_t=i[0]-1
            example = tf.train.Example(features=(tf.train.Features(
                feature={
                    'traindata': _bytes_feature(pixel_t),
                    'trainlabel': _int64_feature(label_t)
                }
            )))
            writer.write(example.SerializeToString())
        writer.close()

        # test data
        test_data_name = os.path.join(self.tfrecords, 'test_data.tfrecords')
        writer = tf.python_io.TFRecordWriter(test_data_name)
        for i in test_pos_all:
            [r, c] = i[1]
            pixel_t = self.neighbor_add(r,c,i[0]-1,w_size=self.cube_size,flag=False).astype(np.float32).tostring()
            #label_t = np.array(np.array(i[0] - 1).astype(np.int64))
            label_t = i[0] - 1
            example = tf.train.Example(features=(tf.train.Features(
                feature={
                    'testdata': _bytes_feature(pixel_t),
                    'testlabel': _int64_feature(label_t)
                }
            )))
            writer.write(example.SerializeToString())
        writer.close()
        return test_pos_all


    def data_parse(self,filename,type='train'):# Generates trainsets and corresponding tags
        dataset = tf.data.TFRecordDataset([filename])
        def parser_train(record):
            keys_to_features = {
                'traindata': tf.FixedLenFeature([], tf.string),
                'trainlabel': tf.FixedLenFeature([], tf.int64),
            }
            features = tf.parse_single_example(record, features=keys_to_features)
            train_data = tf.decode_raw(features['traindata'], tf.float32)
            train_label = tf.cast(features['trainlabel'], tf.int64)
            shape = [self.cube_size,self.cube_size, self.dim]
            train_data = tf.reshape(train_data, shape)
            train_label = tf.reshape(train_label, [1])
            return train_data, train_label
        def parser_test(record): # Generates test sets and corresponding tags
            keys_to_features = {
                'testdata': tf.FixedLenFeature([], tf.string),
                'testlabel': tf.FixedLenFeature([], tf.int64),
            }
            features = tf.parse_single_example(record, features=keys_to_features)
            test_data = tf.decode_raw(features['testdata'], tf.float32)
            test_label = tf.cast(features['testlabel'], tf.int64)
            shape = [self.cube_size,self.cube_size, self.dim]
            test_data = tf.reshape(test_data, shape)
            test_label = tf.reshape(test_label, [1])
            return test_data, test_label

        def parser_all(record):# Corresponding patches of all pixel points are generated
            keys_to_features = {
                'alldata': tf.FixedLenFeature([], tf.string),
            }
            features = tf.parse_single_example(record, features=keys_to_features)
            all_data = tf.decode_raw(features['alldata'], tf.float32)
            shape = [self.cube_size, self.cube_size, self.dim]
            all_data = tf.reshape(all_data, shape)
            return all_data

        if type == 'train':
            dataset = dataset.map(parser_train)
            dataset = dataset.shuffle(buffer_size=20000)
            dataset = dataset.batch(self.args.batch_size)
            dataset = dataset.repeat()
            iterator = dataset.make_one_shot_iterator()
            return iterator.get_next()
        if type == 'test':
            dataset = dataset.map(parser_test)
            dataset = dataset.batch(self.args.test_batch)
            iterator = dataset.make_one_shot_iterator()
            return iterator.get_next()
        if type == 'all':
            dataset = dataset.map(parser_all)
            dataset = dataset.batch(self.args.test_batch)
            iterator = dataset.make_one_shot_iterator()
            return iterator.get_next()

