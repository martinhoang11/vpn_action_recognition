from keras.callbacks import ReduceLROnPlateau, CSVLogger, Callback

from multiprocessing import cpu_count
from NTU_gcnn_Loader import *
from embedding_gcnn_attention_model import *
from compute_adjacency import *
from utils import *

os.environ['KERAS_BACKEND'] = 'tensorflow'
os.environ['CUDA_VISIBLE_DEVICES'] = "0"

epochs = 10
model_name = 'vpn'
protocol = 'cv'
num_classes = 60
batch_size = 4
stack_size = 16
n_neuron = 64
n_dropout = 0.3
timesteps = 16
seed = 8
np.random.seed(seed)

losses = {
    "action_output": "categorical_crossentropy",
    "embed_output": "mean_squared_error",
}
lossWeights = {"action_output": 0.99, "embed_output": 0.01}

optimizers = keras.optimizers.SGD(lr=0.01, momentum=0.9)


class CustomModelCheckpoint(Callback):

    def __init__(self, model_parallel, path):
        super(CustomModelCheckpoint, self).__init__()

        self.save_model = model_parallel
        self.path = path
        self.nb_epoch = 0

    def on_epoch_end(self, epoch, logs=None):
        self.nb_epoch += 1
        self.save_model.save(self.path + str(self.nb_epoch) + '.hdf5')


csv_logger = CSVLogger(model_name + '_ntu.csv')
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.1, patience=5)

alpha = 5
beta = 2
dataset_name = 'NTU'
num_features = 3

if dataset_name == 'NTU':
    num_nodes = 25
elif dataset_name == 'NTU_two':
    num_nodes = 50
else:
    num_nodes = 18

A = compute_adjacency(dataset_name, alpha, beta)
A = np.repeat(A, batch_size, axis=0)
A = np.reshape(A, [batch_size, A.shape[1], A.shape[1]])
SYM_NORM = True
num_filters = 2
graph_conv_filters = preprocess_adj_tensor_with_identity(A, SYM_NORM)

model = embed_model_spatio_temporal_gcnn(n_neuron, timesteps, num_nodes, num_features,
                                         graph_conv_filters.shape[1], graph_conv_filters.shape[2],
                                         num_filters, num_classes, n_dropout, protocol)

paths = {
    'skeleton': '/data/stars/user/achaudha/NTU_RGB/skeleton_npy/',
    'cnn': '/data/stars/user/sdas/NTU_RGB/patches_full_body/',
    'split_path': '/data/stars/user/sdas/NTU_RGB/splits/imp_files/'
}

if protocol == 'CS':
    train = 'train_new'
    test = 'validation_new'
else:
    train = 'train_cross'
    test = 'validation_cross'

model.compile(loss=losses, loss_weights=lossWeights, optimizer=optimizers, metrics=['accuracy'])
train_generator = DataGenerator(paths, graph_conv_filters, timesteps, train, num_classes, stack_size,
                                batch_size=batch_size)
val_generator = DataGenerator(paths, graph_conv_filters, timesteps, test, num_classes, stack_size,
                              batch_size=batch_size)

model_checkpoint = CustomModelCheckpoint(model, './weights_' + model_name + '/epoch_')

model.fit_generator(generator=train_generator,
                    validation_data=val_generator,
                    use_multiprocessing=True,
                    epochs=epochs,
                    callbacks=[csv_logger, model_checkpoint],
                    workers=cpu_count() - 2)
