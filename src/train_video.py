import wandb
from utils import accuracy, my_collate
import numpy as np
import torch
import torch.optim as optim
from dataset_video import MyVideo
from model_video import VideoNN

import torchvision.transforms as transforms

PROJECT_NAME = "temp"
ENTITY = "aidl"

wandb.init(project=PROJECT_NAME, entity=ENTITY)


channel_out1 = 16
pooling1 = 2
kernel_size2 = 3
pooling2 = 2
channel_out3 = 512
kernel_size3 = 3
pooling3 = 2
fr, channels, height, weight = 142, 512, 104, 104

def train_single_epoch_video(model, train_loader, optimizer, device, criterion):
  # Tell wandb to watch what the model gets up to: gradients, weights, and more
  wandb.watch(model, criterion, log="all", log_freq=10)

  model.train()
  
  accs, losses, ypred, yreal = [], [], [], []
  
  for batch_idx, (vid, emo, mask) in enumerate(train_loader):
    optimizer.zero_grad()
    vid, emo, mask = vid.to(device), emo.to(device), mask.to(device)
    # print('running model ...')
    emo_ = model(vid, mask)
    # print('emo_ train: ', emo_.cpu().detach().numpy())
    # print('emo_ train type: ', type(emo_.cpu().detach().numpy()))
    # print('emo: train ', emo.cpu().detach().numpy())
    # print('emo train type: ', type(emo.cpu().detach().numpy()))
    # print('criterion ...')
    # print('emo_ shape: ', emo_.shape)
    # print('emo shape: ', emo.shape)
    
    # confusion_matrix = torch.zeros(pred = pred, labels = labels, batch_ size = params["batch_size"], n_classes = 8)
    # print('logging conf_mat')
    wandb.log({"conf_mat" : wandb.plot.confusion_matrix(probs=emo_.cpu().detach().numpy(), 
                                                        y_true=emo.cpu().detach().numpy(), 
                                                        preds=None, class_names=["neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"])})
    
    loss = criterion(emo_, emo)
    
    # print('bcwrd pass ...')
    loss.backward()
    # print('opt step ...')
    optimizer.step()
    acc = accuracy(emo, emo_)
    losses.append(loss.item())
    accs.append(acc.item())
    ypred.append(emo_.cpu().detach().numpy())
    yreal.append(emo.cpu().detach().numpy())

    return np.mean(losses), np.mean(accs), ypred, yreal

def eval_single_epoch_video(model, val_loader, device, criterion):
  accs, losses, ypred, yreal = [], [], [], []
  with torch.no_grad():
    model.eval()
    for batch_idx, (vid, emo, mask) in enumerate(val_loader):
        vid = vid.to(torch.float32)
        vid = vid.to(device)
        # print('emo: ', emo)
        # print('emo type: ', type(emo))
        # emo = emo.to(torch.float32)
        emo = emo.to(device)
        mask = mask.to(torch.float32)
        mask = torch.Tensor(mask).to(device)
        # vid, emo, mask = vid.to(device), torch.Tensor(emo).to(device), torch.Tensor(mask).to(device)
        # print('running model ...')
        emo_ = model(vid, mask)
        # print('emo_ val: ', emo_)
        # print('emo_ val type: ', type(emo_))
        # print('emo: val', emo)
        # print('emo val type: ', type(emo))
        # print('criterion ...')
        # print('emo_ shape: ', emo_.shape)
        #print('emo_: ', emo_)
        # print('emo shape: ', emo.shape)
        #print('emo: ', emo)
        wandb.log({"conf_mat2" : wandb.plot.confusion_matrix(probs=emo_.cpu().detach().numpy(), 
                                                        y_true=emo.cpu().detach().numpy(), 
                                                        preds=None, class_names=["neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"])})
        loss = criterion(emo_, emo)
        acc = accuracy(emo, emo_)
        losses.append(loss.item())
        accs.append(acc.item())
        ypred.append(emo_.cpu().detach().numpy())
        yreal.append(emo.cpu().detach().numpy())
    return np.mean(losses), np.mean(accs), ypred, yreal

def train_model_video(params, trans_conf, device, criterion, video_path, csv_file_train, csv_file_val, emotion_mapping):
    # tell wandb to get started
  with wandb.init(project=PROJECT_NAME, config=params, entity=ENTITY):
    # access all HPs through wandb.config, so logging matches execution!
    config = wandb.config

    #print("Llegir classe\n")
    train_transforms = transforms.Compose([transforms.CenterCrop(400), transforms.Resize(size = (100, 100))])
    myVideo_train= MyVideo(video_path=video_path, csv_file=csv_file_train, emotion_mapping=emotion_mapping, transform=train_transforms)
    myVideo_val= MyVideo(video_path=video_path, csv_file=csv_file_val, emotion_mapping=emotion_mapping, transform=train_transforms)
    fr, channels, height, weight = myVideo_train[0][0].shape

    #print("Variables video ",fr, channels, height, weight)
    #print("Crear loaders \n")  
    train_loader = torch.utils.data.DataLoader(myVideo_train, batch_size=params['batch_size'], shuffle=params['shuffle'], num_workers=params['num_workers'], collate_fn=my_collate)
    val_loader = torch.utils.data.DataLoader(myVideo_val, batch_size=params['batch_size'], shuffle=params['shuffle'], num_workers=params['num_workers'], collate_fn=my_collate)
    
    #print("Crear model \n")  
    model = VideoNN(num_classes=8, d_model=trans_conf['d_model'], nhead=trans_conf['nhead'],                
                  channels = channels, height = height, weight = weight, 
                  channel_out1 = 16, kernel_size1 = 3, pooling1 = 2,
                  channel_out2 = 32, kernel_size2 = 3, pooling2 = 2,
                  channel_out3 = 32, kernel_size3 = 3, pooling3 = 2, 
                  dim_feedforward=trans_conf['dim_feedforward'],  
                  ).to(device)

    optimizer = optim.Adam(model.parameters(), params["lr"])
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.99)
    # print('LR: ', scheduler.get_last_lr()[0])
    for epoch in range(params["epochs"]):
      loss, acc, ypred_train, yreal_train = train_single_epoch_video(model, train_loader, optimizer, device, criterion)
      wandb.log({"train epoch": epoch, "train loss": loss, "train acc:": acc, "current_lr:": scheduler.get_last_lr()[0]})
      scheduler.step()
      print(f"Train Epoch {epoch} loss={loss:.2f} acc={acc:.2f} current_lr={scheduler.get_last_lr()[0]:.6f}")
      loss, acc, ypred_test, yreal_test = eval_single_epoch_video(model, val_loader, device, criterion)
      wandb.log({"Eval epoch": epoch, "Eval loss": loss, "Eval acc:": acc})
      print(f"Eval Epoch {epoch} loss={loss:.2f} acc={acc:.2f}")
  
  return model, yreal_train, ypred_train, ypred_test, yreal_test