#!/usr/bin/env python3
# Copyright (c) 2022 Lincoln D. Stein (https://github.com/lstein)
# Before running stable-diffusion on an internet-isolated machine,
# run this script from one with internet connectivity. The
# two machines must share a common .cache directory.
#
# Coauthor: Kevin Turner http://github.com/keturn
#
print('Loading Python libraries...\n')
import clip
import sys
import transformers
import os
import warnings
import torch
import urllib.request
import zipfile
import traceback
import getpass
from omegaconf import OmegaConf
from pathlib import Path
from transformers import CLIPTokenizer, CLIPTextModel
from transformers import BertTokenizerFast, AutoFeatureExtractor
from huggingface_hub import hf_hub_download, HfFolder, hf_hub_url

transformers.logging.set_verbosity_error()

#--------------------------globals--
Model_dir = './models/ldm/stable-diffusion-v1/'
Config_file = './configs/models.yaml'
SD_Configs = './configs/stable-diffusion'
Datasets = {
    'stable-diffusion-1.5':  {
        'description': 'The newest Stable Diffusion version 1.5 weight file (4.27 GB)',
        'repo_id': 'runwayml/stable-diffusion-v1-5',
        'config': 'v1-inference.yaml',
        'file': 'v1-5-pruned-emaonly.ckpt',
        'recommended': True,
        'width': 512,
        'height': 512,
    },
    'inpainting-1.5': {
        'description': 'RunwayML SD 1.5 model optimized for inpainting (4.27 GB)',
        'repo_id': 'runwayml/stable-diffusion-inpainting',
        'config': 'v1-inpainting-inference.yaml',
        'file': 'sd-v1-5-inpainting.ckpt',
        'recommended': True,
        'width': 512,
        'height': 512,
    },
    'stable-diffusion-1.4': {
        'description': 'The original Stable Diffusion version 1.4 weight file (4.27 GB)',
        'repo_id': 'CompVis/stable-diffusion-v-1-4-original',
        'config': 'v1-inference.yaml',
        'file': 'sd-v1-4.ckpt',
        'recommended': False,
        'width': 512,
        'height': 512,
    },
    'waifu-diffusion-1.3': {
        'description': 'Stable Diffusion 1.4 fine tuned on anime-styled images (4.27)',
        'repo_id': 'hakurei/waifu-diffusion-v1-3',
        'config': 'v1-inference.yaml',
        'file': 'model-epoch09-float32.ckpt',
        'recommended': False,
        'width': 512,
        'height': 512,
    },
    'ft-mse-improved-autoencoder-840000': {
        'description': 'StabilityAI improved autoencoder fine-tuned for human faces (recommended; 335 MB)',
        'repo_id': 'stabilityai/sd-vae-ft-mse-original',
        'config': 'VAE',
        'file': 'vae-ft-mse-840000-ema-pruned.ckpt',
        'recommended': True,
        'width': 512,
        'height': 512,
    },
}
Config_preamble = '''# This file describes the alternative machine learning models
# available to InvokeAI script.
#
# To add a new model, follow the examples below. Each
# model requires a model config file, a weights file,
# and the width and height of the images it
# was trained on.
'''

#---------------------------------------------
def introduction():
    print(
        '''Welcome to InvokeAI. This script will help download the Stable Diffusion weight files
and other large models that are needed for text to image generation. At any point you may interrupt
this program and resume later.\n'''
    )

#--------------------------------------------
def postscript():
    print(
        '''You're all set! You may now launch InvokeAI using one of these two commands:
Web version: 

    python scripts/invoke.py --web  (connect to http://localhost:9090)

Command-line version:

   python scripts/invoke.py

Have fun!
'''
)

#---------------------------------------------
def yes_or_no(prompt:str, default_yes=True):
    default = "y" if default_yes else 'n'
    response = input(f'{prompt} [{default}] ') or default
    if default_yes:
        return response[0] not in ('n','N')
    else:
        return response[0] in ('y','Y')

#---------------------------------------------
def user_wants_to_download_weights():
    return yes_or_no('Would you like to download the Stable Diffusion model weights now?')

#---------------------------------------------
def select_datasets():
    done = False
    while not done:
        print('''
Choose the weight file(s) you wish to download. Before downloading you 
will be given the option to view and change your selections.
'''
        )
        datasets = dict()

        counter = 1
        dflt = None   # the first model selected will be the default; TODO let user change
        for ds in Datasets.keys():
            recommended = '(recommended)' if Datasets[ds]['recommended'] else ''
            print(f'[{counter}] {ds}:\n    {Datasets[ds]["description"]} {recommended}')
            if yes_or_no('    Download?',default_yes=Datasets[ds]['recommended']):
                datasets[ds]=counter
            counter += 1

        print('The following weight files will be downloaded:')
        for ds in datasets:
            dflt = '*' if dflt is None else ''
            print(f'   [{datasets[ds]}] {ds}{dflt}')
        print("*default")
        ok_to_download = yes_or_no('Ok to download?')
        if not ok_to_download:
            if yes_or_no('Change your selection?'):
                pass
            else:
                done = True
        else:
            done = True
    return datasets if ok_to_download else None
    
#-------------------------------Authenticate against Hugging Face
def authenticate():
    print('''
To download the Stable Diffusion weight files from the official Hugging Face 
repository, you need to read and accept the CreativeML Responsible AI license.

This involves a few easy steps.

1. If you have not already done so, create an account on Hugging Face's web site
   using the "Sign Up" button:

   https://huggingface.co/join

   You will need to verify your email address as part of the HuggingFace
   registration process.

2. Log into your account Hugging Face:

    https://huggingface.co/login

3. Accept the license terms located here:

   https://huggingface.co/CompVis/stable-diffusion-v-1-4-original
'''
    )
    input('Press <enter> when you are ready to continue:')
    access_token = HfFolder.get_token()
    if access_token is None:
        print('''
4. Thank you! The last step is to enter your HuggingFace access token so that
   this script is authorized to initiate the download. Go to the access tokens
   page of your Hugging Face account and create a token by clicking the 
   "New token" button:

   https://huggingface.co/settings/tokens

   (You can enter anything you like in the token creation field marked "Name". 
   "Role" should be "read").

   Now copy the token to your clipboard and paste it here: '''
        )
        access_token = getpass.getpass()
        HfFolder.save_token(access_token)
    return access_token

#---------------------------------------------
# look for legacy model.ckpt in models directory and offer to
# normalize its name
def migrate_models_ckpt():
    if not os.path.exists(os.path.join(Model_dir,'model.ckpt')):
        return
    new_name = Datasets['stable-diffusion-1.4']['file']
    print('You seem to have the Stable Diffusion v4.1 "model.ckpt" already installed.')
    rename = yes_or_no(f'Ok to rename it to "{new_name}" for future reference?')
    if rename:
        print(f'model.ckpt => {new_name}')
        os.rename(os.path.join(Model_dir,'model.ckpt'),os.path.join(Model_dir,new_name))
            
#---------------------------------------------
def download_weight_datasets(models:dict, access_token:str):
    migrate_models_ckpt()
    successful = dict()
    for mod in models.keys():
        repo_id = Datasets[mod]['repo_id']
        filename = Datasets[mod]['file']
        success = conditional_download(
            repo_id=repo_id,
            model_name=filename,
            access_token=access_token
        )
        if success:
            successful[mod] = True
    keys = ', '.join(successful.keys())
    print(f'Successfully installed {keys}') 
    return successful
    
#---------------------------------------------
def conditional_download(repo_id:str, model_name:str, access_token:str):
    model_dest = os.path.join(Model_dir, model_name)
    if os.path.exists(model_dest):
        print(f' * {model_name}: exists')
        return True
    os.makedirs(os.path.dirname(model_dest), exist_ok=True)

    try:
        print(f' * {model_name}: downloading or retrieving from cache...')
        path = Path(hf_hub_download(repo_id, model_name, use_auth_token=access_token))
        path.resolve(strict=True).link_to(model_dest)
    except Exception as e:
        print(f'** Error downloading {model_name}: {str(e)} **')
        return False
    return True
                             
#---------------------------------------------
def update_config_file(successfully_downloaded:dict):
    try:
        yaml = new_config_file_contents(successfully_downloaded)
        tmpfile = os.path.join(os.path.dirname(Config_file),'new_config.tmp')
        with open(tmpfile, 'w') as outfile:
            outfile.write(Config_preamble)
            outfile.write(yaml)
        os.rename(tmpfile,Config_file)
    except Exception as e:
        print(f'**Error creating config file {Config_file}: {str(e)} **')
        return
    print(f'Successfully created new configuration file {Config_file}')

    
#---------------------------------------------    
def new_config_file_contents(successfully_downloaded:dict)->str:
    conf = OmegaConf.load(Config_file)

    # find the VAE file, if there is one
    vae = None
    default_selected = False
    
    for model in successfully_downloaded:
        if Datasets[model]['config'] == 'VAE':
            vae = Datasets[model]['file']
    
    for model in successfully_downloaded:
        if Datasets[model]['config'] == 'VAE': # skip VAE entries
            continue
        stanza = conf[model] if model in conf else { }
        
        stanza['description'] = Datasets[model]['description']
        stanza['weights'] = os.path.join(Model_dir,Datasets[model]['file'])
        stanza['config'] =os.path.join(SD_Configs, Datasets[model]['config'])
        stanza['width'] = Datasets[model]['width']
        stanza['height'] = Datasets[model]['height']
        stanza.pop('default',None)  # this will be set later
        if vae:
            stanza['vae'] = os.path.join(Model_dir,vae)
        # BUG - the first stanza is always the default. User should select.
        if not default_selected:
            stanza['default'] = True
            default_selected = True
        conf[model] = stanza
    return OmegaConf.to_yaml(conf)
    
#---------------------------------------------
# this will preload the Bert tokenizer fles
def download_bert():
    print('Installing bert tokenizer (ignore deprecation errors)...', end='')
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        tokenizer = BertTokenizerFast.from_pretrained('bert-base-uncased')
        print('...success')
        sys.stdout.flush()

#---------------------------------------------
# this will download requirements for Kornia
def download_kornia():
    print('Installing Kornia requirements...', end='')
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        import kornia
    print('...success')

#---------------------------------------------
def download_clip():
    version = 'openai/clip-vit-large-patch14'
    sys.stdout.flush()
    print('Loading CLIP model...',end='')
    tokenizer = CLIPTokenizer.from_pretrained(version)
    transformer = CLIPTextModel.from_pretrained(version)
    print('...success')

#---------------------------------------------
def download_gfpgan():
    print('Installing models from RealESRGAN and facexlib...',end='')
    try:
        from realesrgan import RealESRGANer
        from realesrgan.archs.srvgg_arch import SRVGGNetCompact
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper

        RealESRGANer(
            scale=4,
            model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth',
            model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
        )

        FaceRestoreHelper(1, det_model='retinaface_resnet50')
        print('...success')
    except Exception:
        print('Error loading ESRGAN:')
        print(traceback.format_exc())

    print('Loading models from GFPGAN')
    for model in (
            [
                'https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth',
                'src/gfpgan/experiments/pretrained_models/GFPGANv1.4.pth'
            ],
            [
                'https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth',
                './gfpgan/weights/detection_Resnet50_Final.pth'
            ],
            [
                'https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth',
                './gfpgan/weights/parsing_parsenet.pth'
            ],
    ):
        model_url,model_dest  = model
        try:
            if not os.path.exists(model_dest):
                print(f'Downloading gfpgan model file {model_url}...',end='')
                os.makedirs(os.path.dirname(model_dest), exist_ok=True)
                urllib.request.urlretrieve(model_url,model_dest)
                print('...success')
        except Exception:
            print('Error loading GFPGAN:')
            print(traceback.format_exc())

#---------------------------------------------
def download_codeformer():
    print('Installing CodeFormer model file...',end='')
    try:
            model_url  = 'https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth'
            model_dest = 'ldm/invoke/restoration/codeformer/weights/codeformer.pth'
            if not os.path.exists(model_dest):
                print('Downloading codeformer model file...')
                os.makedirs(os.path.dirname(model_dest), exist_ok=True)
                urllib.request.urlretrieve(model_url,model_dest)
    except Exception:
        print('Error loading CodeFormer:')
        print(traceback.format_exc())
    print('...success')
    
#---------------------------------------------
def download_clipseg():
    print('Installing clipseg model for text-based masking...',end='')
    try:
        model_url  = 'https://owncloud.gwdg.de/index.php/s/ioHbRzFx6th32hn/download'
        model_dest = 'src/clipseg/clipseg_weights.zip'
        weights_dir = 'src/clipseg/weights'
        if not os.path.exists(weights_dir):
            os.makedirs(os.path.dirname(model_dest), exist_ok=True)
            urllib.request.urlretrieve(model_url,model_dest)
            with zipfile.ZipFile(model_dest,'r') as zip:
                zip.extractall('src/clipseg')
                os.rename('src/clipseg/clipseg_weights','src/clipseg/weights')
            os.remove(model_dest)
            from clipseg_models.clipseg import CLIPDensePredT
            model = CLIPDensePredT(version='ViT-B/16', reduce_dim=64, )
            model.eval()
            model.load_state_dict(
                torch.load(
                    'src/clipseg/weights/rd64-uni-refined.pth',
                    map_location=torch.device('cpu')
                    ),
                strict=False,
            )
    except Exception:
        print('Error installing clipseg model:')
        print(traceback.format_exc())
    print('...success')

#-------------------------------------
def download_safety_checker():
    print('Installing safety model for NSFW content detection...',end='')
    try:
        from diffusers.pipelines.stable_diffusion.safety_checker import StableDiffusionSafetyChecker
    except ModuleNotFoundError:
        print('Error installing safety checker model:')
        print(traceback.format_exc())
        return
    safety_model_id = "CompVis/stable-diffusion-safety-checker"
    safety_feature_extractor = AutoFeatureExtractor.from_pretrained(safety_model_id)
    safety_checker = StableDiffusionSafetyChecker.from_pretrained(safety_model_id)
    print('...success')
    
#-------------------------------------
if __name__ == '__main__':
    try:
        introduction()
        print('** WEIGHT SELECTION **')
        if user_wants_to_download_weights():
            models = select_datasets()
            if models is None:
                if yes_or_no('Quit?',default_yes=False):
                    sys.exit(0)
            print('** LICENSE AGREEMENT FOR WEIGHT FILES **')
            access_token = authenticate()
            print('\n** DOWNLOADING WEIGHTS **')
            successfully_downloaded = download_weight_datasets(models, access_token)
            update_config_file(successfully_downloaded)
        print('\n** DOWNLOADING SUPPORT MODELS **')
        download_bert()
        download_kornia()
        download_clip()
        download_gfpgan()
        download_codeformer()
        download_clipseg()
        download_safety_checker()
        postscript()
    except KeyboardInterrupt:
        print("\nGoodbye! Come back soon.")


    
