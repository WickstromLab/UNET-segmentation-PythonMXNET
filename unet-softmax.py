# U-ConvNet for segmentation of aggregates

print("""The script is a Python implementation of UConvNet for image segmentation. We provide a labeled training dataset to
train the neural net. The script makes use of MXNET library/APIs, functions from OpenCV (CLAHE) and the python libraries:
numpy, matplotlib, os and PIL\n
/**
 * @author :Ali Hashmi
 *
 *  code is based of "https://lmb.informatik.uni-freiburg.de/people/ronneber/u-net/" :
 */\n""")

############ importing all relevant modules ############
import mxnet as mx, os, numpy as np, matplotlib.pyplot as plt, cv2, logging, random
from PIL import Image
logging.getLogger().setLevel(logging.INFO) # log the training session
from collections import namedtuple
Batch = namedtuple('Batch', ['data'])

############ context ###################################
device_context = mx.gpu(0); """set device on which the traning will be perfomed, use mx.cpu() for training over CPU cores, however,
Note: training over CPU will be considerably slower (3 hours on a an 8 core machine) compared to a 7 minutes on my GPU (640 cores).
Yes the difference is astounding ! """;

print("version of MXNET: ", mx.__version__," -> with context set to: ", device_context,"\n")

############# global constants & HyperParamaters ###################
width,height = (168,168)    #images and masks will be resized according to the following tuple
filtercount = 32
directory = 'C:\\Users\\aliha\\Downloads\\fabrice-ali\\deeplearning\\';
kernel_size = (3,3) #kernel size for convolutions
pad_size = (1,1) #padding for convolutions
initializer = mx.initializer.Normal(np.sqrt(2. / 576))
num_round = 48; #number of epochs (for training rounds)
batch_size = 8; #batch-size to process
fractionalp = 2/3; #training-dataset/testing-dataset ratio
lr = 0.01;  #learning rate
drop = 0.5; #drop from the DropOut layer, optimal between 0.2 to 0.5
optimizer = 'nadam'  # other possible options are: 'sgd' (stochastic gradient descent) etc..
optimizerdict = {'learning_rate': lr}
applynet,train,retrain = (True,False,False)
(start_epoch,step_epochs) = (48,3) # for retraining the network
test_img = "C:\\Users\\aliha\Downloads\\fabrice-ali\\deeplearning\\data\\train\\train_images_8bit\\image225.tif";

############## setting directory #################
if(os.getcwd() != directory):
    os.chdir(directory)
training_image_directory = directory + "data\\train\\train_images_8bit\\";
imagefilenames = os.listdir(training_image_directory) # list of all images in the directory
training_label_directory = directory + "data\\train\\train_masks\\"
maskfilenames = os.listdir(training_label_directory) # list of all masks in the directory

######### function definitions ########################
def inferred_shape(net):
    """ extracts dimensions/shapes of the various layers """
    global width,height
    _,out_shapes,__ = net.infer_shape(data = (batch_size,1,width,height))
    return out_shapes

def printshape(str,net):
    """ wrapper for printing layer shapes """
    print(str,inferred_shape(net))

def convolution_module(net, kernel_size, pad_size, filter_count, stride = (1, 1), work_space = 2048, batch_norm = True,
 down_pool = False, up_pool = False, act_type = "relu", convolution = True):
                       """ as specified by the name of the function, for convolutions """
                       if up_pool:
                           net = mx.symbol.Deconvolution(net, kernel = (2, 2), pad = (0, 0), stride = (2, 2),
                                                         num_filter = filter_count, workspace = work_space);
                           net = mx.symbol.BatchNorm(net)
                           if act_type != "":
                               net = mx.symbol.Activation(net, act_type = act_type)
                       if convolution:
                           conv = mx.symbol.Convolution(data = net, kernel = kernel_size, stride = stride,
                                                    pad = pad_size, num_filter = filter_count, workspace = work_space)
                           net = conv
                       if batch_norm:
                           net = mx.symbol.BatchNorm(net)
                       if act_type != "":
                           net = mx.symbol.Activation(net, act_type = act_type)
                       if down_pool:
                           pool = mx.symbol.Pooling(net, pool_type = "max", kernel = (2, 2), stride = (2, 2));
                           net = pool
                       printshape("convolution module: ", net)
                       return net

def get_unet():
    """ generate symbolic neural network -> U-net"""
    data = mx.symbol.Variable('data')
    global filtercount, kernel_size, pad_size
    pool1 = convolution_module(data, kernel_size, pad_size, filter_count = filtercount, down_pool = True)
    net = pool1
    pool2 = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 2, down_pool = True)
    net = pool2
    pool3 = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 4, down_pool = True)
    net = pool3
    pool4 = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 4, down_pool = True)
    net = pool4
    printshape("before dropout: ",net)
    net = mx.symbol.Dropout(net, p = drop)
    printshape("after dropout: ", net)
    pool5 = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 8, down_pool = True)
    net = pool5
    net = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 4, up_pool = True)
    net = convolution_module(net, kernel_size, pad_size = (2, 2), filter_count = filtercount * 4, up_pool = True)
    printshape("before cropping: ", net)
    net = mx.symbol.Crop(net, pool3)
    printshape("after cropping: ", net)
    net = mx.symbol.Concat(pool3,net)
    printshape("after concat: ", net)
    net = mx.symbol.Dropout(net, p = drop)
    printshape("after dropout; ", net)
    net = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 4)
    net = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 4, up_pool = True)
    printshape("before concat: ", net)
    net = mx.symbol.Concat(pool2, net)
    printshape("after concat: ", net)
    net = mx.symbol.Dropout(net, p = drop)
    printshape("after dropout: ", net)
    net = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 4)
    net = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 4, up_pool = True)
    printshape("before concat: ", net)
    net = mx.symbol.Concat(pool1, net)
    printshape("after concat: ", net)
    net = mx.symbol.Dropout(net, p = drop)
    printshape("after dropout: ", net)
    net = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 2)
    net = convolution_module(net, kernel_size, pad_size, filter_count = filtercount * 2, up_pool = True)
    net = convolution_module(net, kernel_size, pad_size, filter_count = 1, batch_norm = False, act_type = "")
    net = mx.symbol.SoftmaxOutput(data = net, name = 'softmax')
    printshape("out: ", net)
    print("\n")
    return net

############### image-processing and miscellaneous routines to generate training and test datasets ###################
def claheResize(imagefile):
    """ contrast limited adaptive histogram equalization from OPENCV and image resizing """
    global width, height
    img = cv2.imread(imagefile,0)
    clahe = cv2.createCLAHE().apply(img)
    return Image.fromarray(clahe).resize((width,height),Image.ANTIALIAS)

def imageResize(imgfilename, is8bit = True):
    """ takes in an image filename and outputs a resized version of the image with antialiasing """
    global width, height
    if not(is8bit):
        img = cv2.imread(imgfilename,cv2.IMREAD_UNCHANGED)
        img = img.astype('uint8')
        img = Image.fromarray(img)
        return img.resize((width,height),Image.ANTIALIAS)
    else:
        img = Image.open(imgfilename)
        return img.resize((width,height),Image.ANTIALIAS)

# load and resize labels -> ensure binary images
imagefilenames = list(map(lambda x: training_image_directory + x, imagefilenames))
maskfilenames = list(map(lambda x: training_label_directory + x, maskfilenames))
imagefilenames = imagefilenames[0:320] # considering a subset of data and corresponding labels
maskfilenames = maskfilenames[0:320]

##### Resize images
#train_x = np.asarray(list(map(lambda x: np.array(imageResize(x,binarized=False)), imagefilenames)))
train_x = np.asarray([np.array(imageResize(imagefilenames[i])) for i in range(len(imagefilenames))])

##### image resizing with CLAHE OpenCV
#train_x = np.asarray(list(map(lambda x: np.array(claheResize(x)),imagefilenames))) """ same as below, just more functional in nature"""
#train_x = np.asarray([np.array(claheResize(imagefilenames[i])) for i in range(len(imagefilenames))])

##### Resize Masks/Labels
#train_y = np.asarray(list(map(lambda x: np.array(imageResize(x)),maskfilenames)))
train_y = np.asarray([np.array(imageResize(maskfilenames[i])) for i in range(len(maskfilenames))])
train_y[train_y >= 1] = 1; # ensure binarization
train_y[train_y < 1] = 0;

# splitting datasets to training and testing halves
N = len(maskfilenames)
n = int(np.floor(N*fractionalp)) # adjust fractionalp to change the training/testing datasets lengths
print("length of training dataset:", n, " samples")
print("length of validation dataset:", N-n, " samples\n")

assert len(train_x) == len(train_y)
train_x = train_x.reshape((len(train_x),1, width, height)) # array reshaping required for data and labels
train_y = train_y.reshape((len(train_y),1, width, height))
train_x_array, test_x_array = (train_x[:n], train_x[n:])
train_y_array, test_y_array = (train_y[:n], train_y[n:])

################### Learning Factory ###################
os.chdir(directory + "saved_models\\") # where do you want to save the training model
print("### Architecture of U-net ###\n")

net = get_unet() # generate the symbolic network (uninitialized)
#mx.viz.plot_network(net, save_format = 'pdf').render() # uncomment to visualize the neural network -> check directory for save

# internal metrics can be used, in contrast build custom metrics if need-be
def custom_rmse(label,pred):
    return np.sqrt(np.mean((label-pred)**2))

def custom_logloss(label,pred):
    res = np.mean((label*np.log(pred)) + ((1-label)*np.log(1-pred)))
    return res

metric_internal = mx.metric.create(['acc','rmse'])
metric_custom_rmse = mx.metric.CustomMetric(feval = custom_rmse)
metric_logloss_Custom = mx.metric.CustomMetric(feval = custom_logloss)
rounded_mean_err = lambda labels, predictors : np.mean(np.abs(labels-np.round(predictors)))
metric_rmse_Custom_rounded = mx.metric.CustomMetric(feval = rounded_mean_err)

train_iter = mx.io.NDArrayIter(data = {'data': train_x_array}, label = {'softmax_label': train_y_array},
 batch_size = batch_size) ;""" generate iterations over training set"""
val_iter = mx.io.NDArrayIter(data = test_x_array, label = test_y_array, batch_size = batch_size); """ generate iterations over
validation/testing set """


# training the network-model
if train:
    model = mx.module.Module(symbol=net, context = device_context)
    model.fit(
        train_data = train_iter,
        eval_data = val_iter,
        optimizer = optimizer,
        initializer = initializer,
        optimizer_params=optimizerdict,
        eval_metric ='acc',
        num_epoch = num_round
        )
    model.save_checkpoint("blobseg_model", num_round)

############## Supplementary procedures ################

#### retrain the network-model if necessary

if retrain:
    iteration = str(start_epoch)
    os.chdir(directory + "saved_models\\saved\\iteration " + iteration)
    model_prefix = "blobseg_model"
    symbolicNet, arg_params, aux_params = mx.model.load_checkpoint(model_prefix, start_epoch)
    model = mx.module.Module(symbol = symbolicNet, context = device_context)
    model.fit(
    train_data = train_iter,
    eval_data = val_iter,
    arg_params = arg_params,
    aux_params = aux_params,
    optimizer = optimizer,
    num_epoch = step_epochs,
    optimizer_params = optimizerdict,
    eval_metric ='acc'
    )
    num_round = start_epoch + step_epochs
    os.chdir(directory + "saved_models\\")
    model.save_checkpoint(model_prefix,num_round)

#### load the pretrained network and apply over an image

def printOutput(matrix):
    """ matrix printout function to display output matrix """
    plt.matshow(matrix)
    plt.show()

if applynet:
    os.chdir(directory + "saved_models\\saved\\iteration " + str(num_round))
    model_prefix = "blobseg_model"
    testimgdata = np.asarray(imageResize(test_img)).reshape((1,1,width,height))

    symbolicNet, arg_params, aux_params = mx.model.load_checkpoint(model_prefix,num_round) # loading the trained network
    all_layers = symbolicNet.get_internals()   # retrieve all the layers of the network symbolically
    print("printing last 10 NET-layers:", all_layers.list_outputs()[-10:],"\n") #printing the last 10 symbolic-layers of the network
    fe_sym = all_layers['softmax_output'] # ->  OUTPUT function
    fe_mod = mx.mod.Module(symbol = fe_sym, context = device_context, label_names=None) # feeding output layer to the net
    fe_mod.bind(for_training=False, data_shapes=[('data', (1,1,width,height))]) # binding data for testing-phase
    fe_mod.set_params(arg_params, aux_params, allow_missing=True)     # assigning weights/gradients to the uninitialized layers
    fe_mod.forward(Batch([mx.nd.array(testimgdata)]))           # apply the net on the input image
    features = fe_mod.get_outputs()[0].asnumpy()        # output tensor
    features[features>0] = 255                          # for non-zero probabilities assign 255 (white)
    #printOutput(features[0][0])
    mask = np.array(features[0][0],dtype='uint8')       # peal tensor to get the matrix
    maskimg = Image.fromarray(mask)                     # create image
    maskimg.show()                                      # display
    maskimg.save("C:/Users/aliha/Desktop/segmentationOutput.tif") # save segmentation mask