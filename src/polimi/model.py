from keras.layers import Add, BatchNormalization, Input, Dense, Activation, Concatenate, Conv1D, MaxPool1D, \
    GlobalAveragePooling1D, SpatialDropout1D, Conv2D, MaxPool2D, Flatten, Lambda
from keras.models import Model
from keras.optimizers import RMSprop
import params


def SimpleBlock(inputs, hidden_features=128, kernel_dim=3):
    x = inputs

    x = Conv1D(hidden_features, kernel_dim, strides=1, padding='same')(x)
    x = BatchNormalization()(x)
    x = SpatialDropout1D(0.5)(x)
    x = Activation("relu")(x)

    return x


def ResBlock(inputs, hidden_features=128, kernel_dim=3):
    x = inputs
    x_short = inputs

    x_short = MaxPool1D(pool_size=2, strides=2, padding='same')(x_short)
    x_short = BatchNormalization()(x_short)

    x = Conv1D(hidden_features, kernel_dim, strides=1, padding='same')(x)
    x = SpatialDropout1D(0.5)(x)
    x = Conv1D(hidden_features, kernel_dim, strides=1, padding='same')(x)
    x = SpatialDropout1D(0.5)(x)

    x = MaxPool1D(pool_size=2, strides=2, padding='same')(x)
    x = BatchNormalization()(x)

    x = Add()([x, x_short])
    x = Activation("relu")(x)

    return x


def get_pathosnet_voice(pathosnet_weights_path=None, verbose=False):
    if verbose:
        print("\tInstantiating PATHOSnet Voice...")

    input_audio_vggish = Input(shape=(None, 128))
    input_audio_ghost = Input(shape=(None, 512))

    x1 = input_audio_vggish
    x3 = input_audio_ghost

    inputs = [input_audio_vggish, input_audio_ghost]

    # VGGish -----------------------------------------------------------------------------------------------------------

    # AUDIO BRANCH
    # First Simple Convolution Block
    x1 = SimpleBlock(x1, hidden_features=256, kernel_dim=3)
    x1 = MaxPool1D(pool_size=2, strides=2, padding='same')(x1)
    x1 = BatchNormalization(axis=-1)(x1)
    # ResNet Convolution Blocks
    x1 = ResBlock(x1, hidden_features=256, kernel_dim=3)
    x1 = ResBlock(x1, hidden_features=256, kernel_dim=3)
    # Flatten Information
    x_vggish = GlobalAveragePooling1D()(x1)

    # Thin-ResNet GhostVLAD --------------------------------------------------------------------------------------------

    # AUDIO BRANCH
    # First Simple Convolution Block
    x3 = SimpleBlock(x3, hidden_features=256, kernel_dim=3)
    x3 = MaxPool1D(pool_size=2, strides=2, padding='same')(x3)
    x3 = BatchNormalization(axis=-1)(x3)
    # ResNet Convolution Blocks
    x3 = ResBlock(x3, hidden_features=256, kernel_dim=3)
    x3 = ResBlock(x3, hidden_features=256, kernel_dim=3)
    # Flatten Information
    x_ghost = GlobalAveragePooling1D()(x3)

    # Features Concatenation from models -------------------------------------------------------------------------------
    x = Concatenate(axis=1)([x_vggish, x_ghost])
    x = Lambda(lambda h: h / params.TEMPERATURE)(x)

    # OUTPUT
    outputs = Dense(4, activation="softmax")(x)

    # MODEL
    model = Model(inputs=inputs, outputs=outputs)
    if pathosnet_weights_path is not None:
        if verbose:
            print("\tLoading PATHOSnet weights...")
        model.load_weights(pathosnet_weights_path)
        model.trainable = False
        if verbose:
            print("\tPATHOSnet weights loaded successfully.")
    model.compile(loss='categorical_crossentropy', optimizer=RMSprop(lr=0.001, rho=0.9, decay=0.0),
                  metrics=['categorical_accuracy'])
    if verbose:
        print("\tPATHOSnet instantiated successfully.")
    return model


def get_pathosnet_multimodal(pathosnet_weights_path=None, verbose=False):
    if verbose:
        print("\tInstantiating PATHOSnet Multimodal...")

    input_audio_vggish = Input(shape=(None, 128))
    input_audio_ghost = Input(shape=(None, 512))
    input_text_vggish = Input(shape=(None, 300))
    input_text_ghost = Input(shape=(None, 300))

    x1 = input_audio_vggish
    x2 = input_text_vggish
    x3 = input_audio_ghost
    x4 = input_text_ghost

    inputs = [input_audio_vggish, input_text_vggish, input_audio_ghost, input_text_ghost]

    # VGGish -----------------------------------------------------------------------------------------------------------

    # AUDIO BRANCH
    # First Simple Convolution Block
    x1 = SimpleBlock(x1, hidden_features=256, kernel_dim=3)
    x1 = MaxPool1D(pool_size=2, strides=2, padding='same')(x1)
    x1 = BatchNormalization(axis=-1)(x1)
    # ResNet Convolution Blocks
    x1 = ResBlock(x1, hidden_features=256, kernel_dim=3)
    x1 = ResBlock(x1, hidden_features=256, kernel_dim=3)
    # Flatten Information
    x1 = GlobalAveragePooling1D()(x1)

    # TEXT BRANCH
    # First Simple Convolution Block
    x2 = SimpleBlock(x2, hidden_features=128, kernel_dim=3)
    x2 = MaxPool1D(pool_size=2, strides=2, padding='same')(x2)
    x2 = BatchNormalization(axis=-1)(x2)
    # ResNet Convolution Blocks
    x2 = ResBlock(x2, hidden_features=128, kernel_dim=3)
    x2 = ResBlock(x2, hidden_features=128, kernel_dim=3)
    # Flatten Information
    x2 = GlobalAveragePooling1D()(x2)

    # Features Concatenation
    x_vggish = Concatenate(axis=1)([x1, x2])

    # Thin-ResNet GhostVLAD --------------------------------------------------------------------------------------------

    # AUDIO BRANCH
    # First Simple Convolution Block
    x3 = SimpleBlock(x3, hidden_features=256, kernel_dim=3)
    x3 = MaxPool1D(pool_size=2, strides=2, padding='same')(x3)
    x3 = BatchNormalization(axis=-1)(x3)
    # ResNet Convolution Blocks
    x3 = ResBlock(x3, hidden_features=256, kernel_dim=3)
    x3 = ResBlock(x3, hidden_features=256, kernel_dim=3)
    # Flatten Information
    x3 = GlobalAveragePooling1D()(x3)

    # TEXT BRANCH
    # First Simple Convolution Block
    x4 = SimpleBlock(x4, hidden_features=128, kernel_dim=3)
    x4 = MaxPool1D(pool_size=2, strides=2, padding='same')(x4)
    x4 = BatchNormalization(axis=-1)(x4)
    # ResNet Convolution Blocks
    x4 = ResBlock(x4, hidden_features=128, kernel_dim=3)
    x4 = ResBlock(x4, hidden_features=128, kernel_dim=3)
    # Flatten Information
    x4 = GlobalAveragePooling1D()(x4)
    # Features Concatenation
    x_ghost = Concatenate(axis=1)([x3, x4])

    # Features Concatenation from models -------------------------------------------------------------------------------
    x = Concatenate(axis=1)([x_vggish, x_ghost])
    x = Lambda(lambda h: h / params.TEMPERATURE)(x)

    # OUTPUT
    outputs = Dense(4, activation="softmax")(x)

    # MODEL
    model = Model(inputs=inputs, outputs=outputs)
    if pathosnet_weights_path is not None:
        if verbose:
            print("\tLoading PATHOSnet weights...")
        model.load_weights(pathosnet_weights_path)
        model.trainable = False
        if verbose:
            print("\tPATHOSnet weights loaded successfully.")
    model.compile(loss='categorical_crossentropy', optimizer=RMSprop(lr=0.001, rho=0.9, decay=0.0),
                  metrics=['categorical_accuracy'])
    if verbose:
        print("\tPATHOSnet instantiated successfully.")
    return model


def get_vggish(vggish_weights_path, verbose=False):
    if verbose:
        print("\tInstantiating VGGish...")
    kernel = 3
    inputs = Input(shape=(96, 64, 1))
    x = Conv2D(64, kernel, strides=1, padding='same', activation='relu',trainable=False)(inputs)
    x = MaxPool2D(pool_size=2, strides=2, padding='same')(x)
    x = Conv2D(128, kernel, strides=1, padding='same', activation='relu',trainable=False)(x)
    x = MaxPool2D(pool_size=2, strides=2, padding='same')(x)
    x = Conv2D(256, kernel, strides=1, padding='same', activation='relu',trainable=False)(x)
    x = Conv2D(256, kernel, strides=1, padding='same', activation='relu',trainable=False)(x)
    x = MaxPool2D(pool_size=2, strides=2, padding='same')(x)
    x = Conv2D(512, kernel, strides=1, padding='same', activation='relu',trainable=False)(x)
    x = Conv2D(512, kernel, strides=1, padding='same', activation='relu',trainable=False, name="vgg_to_train")(x)
    x = MaxPool2D(pool_size=2, strides=2, padding='same')(x)
    x = Flatten()(x)
    x = Dense(4096, activation="relu")(x)
    x = Dense(4096, activation="relu")(x)
    outputs = Dense(128, activation="softmax")(x)
    vggish = Model(inputs, outputs)
    # vggish = vggish_keras.get_vggish_keras()
    if verbose:
        print("\tLoading VGGish weights...")
    vggish.load_weights(vggish_weights_path)
    vggish.trainable = False
    if verbose:
        print("\tVGGish weights loaded successfully.")
    if verbose:
        print("\tVGGish instantiated successfully.")
    return vggish
