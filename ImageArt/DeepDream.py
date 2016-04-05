__author__ = 'Charlie'
# Attempt to learn alignment info given image and its reference

import tensorflow as tf
import numpy as np
import scipy.io
import scipy.misc
from datetime import datetime
import os, sys, inspect

utils_path = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile(inspect.currentframe()))[0], "..")))
if utils_path not in sys.path:
    sys.path.insert(0, utils_path)

import TensorflowUtils as utils

FLAGS = tf.flags.FLAGS
tf.flags.DEFINE_string("image_path", "", """Path to image to be dreamed""")
tf.flags.DEFINE_string("model_dir", "Models_zoo/", """Path to the VGGNet model mat file""")
tf.flags.DEFINE_string("log_dir", "logs/Deepdream_logs/", """Path to save logs and checkpoint if needed""")

DATA_URL = 'http://www.vlfeat.org/matconvnet/models/beta16/imagenet-vgg-verydeep-19.mat'

LEARNING_RATE = 1e-2
MAX_ITERATIONS = 1000
DREAM_LAYER = "relu5_4"


def get_model_data():
    filename = DATA_URL.split("/")[-1]
    filepath = os.path.join(FLAGS.model_dir, filename)
    if not os.path.exists(filepath):
        raise IOError("VGGNet Model not found!")
    data = scipy.io.loadmat(filepath)
    return data


def get_image(image_dir):
    image = scipy.misc.imread(image_dir)
    image = np.ndarray.reshape(image.astype(np.float32), (((1,) + image.shape)))
    return image


def vgg_net(weights, image):
    layers = (
        'conv1_1', 'relu1_1', 'conv1_2', 'relu1_2', 'pool1',

        'conv2_1', 'relu2_1', 'conv2_2', 'relu2_2', 'pool2',

        'conv3_1', 'relu3_1', 'conv3_2', 'relu3_2', 'conv3_3',
        'relu3_3', 'conv3_4', 'relu3_4', 'pool3',

        'conv4_1', 'relu4_1', 'conv4_2', 'relu4_2', 'conv4_3',
        'relu4_3', 'conv4_4', 'relu4_4', 'pool4',

        'conv5_1', 'relu5_1', 'conv5_2', 'relu5_2', 'conv5_3',
        'relu5_3', 'conv5_4', 'relu5_4'
    )

    net = {}
    current = image
    for i, name in enumerate(layers):
        kind = name[:4]
        if kind == 'conv':
            kernels, bias = weights[i][0][0][0][0]
            # matconvnet: weights are [width, height, in_channels, out_channels]
            # tensorflow: weights are [height, width, in_channels, out_channels]
            kernels = np.transpose(kernels, (1, 0, 2, 3))
            bias = bias.reshape(-1)
            current = utils.conv2d_basic(current, kernels, bias)
        elif kind == 'relu':
            current = tf.nn.relu(current)
        elif kind == 'pool':
            current = utils.max_pool_2x2(current)
        elif kind == 'norm':
            current = tf.nn.lrn(current, 4, bias=1.0, alpha=0.001 / 9.0, beta=0.75)

        net[name] = current

    assert len(net) == len(layers)
    return net


def main(argv=None):
    utils.maybe_download_and_extract(FLAGS.model_dir, DATA_URL)
    model_data = get_model_data()
    dream_image = get_image(FLAGS.image_path)
    print dream_image.shape

    mean = model_data['normalization'][0][0][0]
    mean_pixel = np.mean(mean, axis=(0, 1))

    processed_image = utils.process_image(dream_image, mean_pixel)
    weights = np.squeeze(model_data['layers'])

    dummy_image = tf.Variable(processed_image)
    tf.histogram_summary("Image_Output", dummy_image)
    dream_net = vgg_net(weights, dummy_image)

    with tf.Session() as sess:
        dream_layer_features = dream_net[DREAM_LAYER]
        max_value = tf.reduce_max(dream_layer_features)
        dream_layer_features = tf.sub(max_value, dream_layer_features)
        # loss = tf.sqrt(2 * tf.nn.l2_loss(dream_layer_features)) / utils.get_tensor_size(dream_layer_features)
        # tf.scalar_summary("Loss", loss)

        summary_op = tf.merge_all_summaries()
        train_op = tf.train.AdamOptimizer(LEARNING_RATE).minimize(dream_layer_features)

        best_loss = float('inf')
        best = None
        summary_writer = tf.train.SummaryWriter(FLAGS.log_dir)
        sess.run(tf.initialize_all_variables())

        for i in range(1, MAX_ITERATIONS):
            train_op.run()

            if i % 10 == 0 or i == MAX_ITERATIONS - 1:
                this_loss = max_value.eval()
                print('Step %d' % (i)),
                print('    total loss: %g' % this_loss)
                summary_writer.add_summary(summary_op.eval(), global_step=i)
                if this_loss < best_loss:
                    best_loss = this_loss
                    best = dummy_image.eval()
                    output = utils.unprocess_image(best.reshape(dream_image.shape[1:]), mean_pixel)
                    scipy.misc.imsave("dream_check.jpg", output)

    output = utils.unprocess_image(best.reshape(dream_image.shape[1:]), mean_pixel)
    scipy.misc.imsave("output.jpg", output)


if __name__ == "__main__":
    tf.app.run()
