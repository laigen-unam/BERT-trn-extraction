#!/usr/bin/env python
# coding: utf-8

# # BioLinkBERT for classification of regulation type

# ## Libraries

# In[21]:


import pandas as pd
# For spliting training, validation and test groups
from sklearn.model_selection import train_test_split
# For creating the batches for training 
from torch.utils.data import Dataset, DataLoader
# Deep learning framework
import torch
# Optimizer for the fine-tunning steps
from transformers import AdamW
# Model construction framework
import pytorch_lightning as pl
# Download existing tokenizer for the selected model 
from transformers import AutoTokenizer
# Download the pretrained model with a classification head on top
from transformers import AutoModelForSequenceClassification
# Live performance metrics of the model
import wandb
import torchmetrics
# Meassuring performance of the model F1-score
from torchmetrics.classification import MulticlassF1Score
#from sklearn.metrics import confusion_matrix
import numpy as np 
# Heatmap for confusion matrix 
import seaborn as sn
# Meassuring actual vs predicted groups
from torchmetrics.classification import ConfusionMatrix
# Plotting confusion matrix 
import matplotlib.pyplot as plt
from pytorch_lightning import Trainer
from pytorch_lightning.loggers import WandbLogger
from pytorch_lightning.callbacks import EarlyStopping


# In[22]:


# Setting a seed for random operations reproducibility 
torch.manual_seed(12222) 


# In[23]:


# curated data but multi regultor - multi regulated
#data = pd.read_pickle("../../01_preprocessing/results/ECO/curated_master_dataset/ECO_dataset_master_curated_whole_tagging_info_with_span_data_serialized_4_v2.pkl")

# for ascend server running 
data = pd.read_pickle("../data/ECO_dataset_master_curated_whole_tagging_info_with_span_data_serialized_4_v2.pkl")


# In[24]:


data.columns


# In[25]:


df = data.filter(['sentence_tagged','NORMALIZED_EFFECT'], axis=1)

df.rename(columns = {"sentence_tagged":"sentence","NORMALIZED_EFFECT":"label"},
               inplace = True)


# In[26]:


print(df)


# In[27]:


id2label = dict()
for idx, label in enumerate(df.label.value_counts().index):
  id2label[idx] = label
print(id2label)


# In[ ]:


# For test confusion matrix
class_conf_labels = []
for keys, values in id2label.items():
    class_conf_labels.append(values)

print(class_conf_labels)


# In[28]:


label2id = {v:k for k,v in id2label.items()}
print(label2id)


# ## Tokenization

# In[29]:


# We use this tokenizer from transformer library to turn the dataset into the inputs expected by the model 
# Specifing the model max length as it is not defined by the model 
tokenizer = AutoTokenizer.from_pretrained("michiyasunaga/BioLinkBERT-base",model_max_length=512)


class RelationExtractionDataset(Dataset):
    """Relation extraction dataset."""

    def __init__(self, data):
        """
        Args:
            data : Pandas dataframe.
        """
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data.iloc[idx]

        sentence = item.sentence
#        entity_spans = [tuple(x) for x in item.entity_spans]
        
#### Tokenization step
# return_tensors: Specify the type of tensors we want to get back (PyTorch, TensorFlow, or plain NumPy)
# padding: Tensors, the input of the model need to have a uniform shape but the sentences are not the same length with this we add a special token to the sentences that are shorter to ensure tensors are rectangular
# padding true is to max sentence length because this tokenizer does not padd with a max length by itself
# truncation: Sometimes a sequence may be too long for a model to handle. In this case we truncate the sentence to a shorter length. True, truncate a sequence to the maximum length accepted by the model 
        encoding = tokenizer(sentence, padding="max_length", truncation=True, return_tensors="pt")

        for k,v in encoding.items():
          # squeeze removes dimensions with size 1 ensuring that tensors have the expected shape
          encoding[k] = encoding[k].squeeze()

        encoding["label"] = torch.tensor(label2id[item.label])

        return encoding


# ### Splitting into random train and test subsets

# In[30]:


# 80% train and 20% test
train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, shuffle=True)
train_df, val_df = train_test_split(train_df, test_size=0.2, random_state=42, shuffle=False)

print("length train dataset : {}".format(len(train_df)))
print("length validation dataset: {}".format(len(val_df)))
print("length test dataset: {}".format(len(test_df)))

# define the dataset and tokenization
train_dataset = RelationExtractionDataset(data=train_df)
valid_dataset = RelationExtractionDataset(data=val_df)
test_dataset = RelationExtractionDataset(data=test_df)


# In[31]:


print("train_dataset: {}".format(train_dataset))
print("valid_dataset: {}".format(valid_dataset))
print("test_dataset: {}".format(test_dataset))


# In[32]:


print("train_dataset.keys: {}".format(train_dataset[0].keys()))
print("input_ids lenght: {}".format(len(train_dataset[0]["input_ids"])))
print("train_dataset.values: {}".format(train_dataset[0].values()))

print("length train dataset : {}".format(len(train_dataset)))
print("length validation dataset: {}".format(len(valid_dataset)))
print("length test dataset: {}".format(len(test_dataset)))


# ### Looking into the tokenizer

# In[33]:


print("Tokenizer information: \n {}".format(tokenizer))
print("Tokenizer vocabulary size: {}".format(tokenizer.vocab_size))


# In[34]:


# Get the first 10 elements of the tokenizer vocabulary 
vocab = tokenizer.get_vocab()
print("vocab keys are the words of the vocabulary: {}".format(list(vocab.keys())[:10]))
print("vocab values are the input_ids: {}".format(list(vocab.values())[:10]))
# Checking if a word is in the vocabulary 
print('Is "ArgP" in vocabulary?: {}'.format("ArgP" in vocab.keys()))
print('Is "this" in vocabulary?: {}'.format("this" in vocab.keys()))
print('input_id of "this": {}'.format(vocab["this"]))


# ### Defining the dataloaders for eficient loading and iterating over the data in batches during the training and evaluation

# In[35]:


# We will use 10,16,32 and 64
#train_dataloader = DataLoader(train_dataset, batch_size=10, shuffle=True)
#valid_dataloader = DataLoader(valid_dataset, batch_size=10)
#test_dataloader = DataLoader(test_dataset, batch_size=10)


# In[36]:


#print("length train dataloader : {}".format(len(train_dataloader)))
#print("length validation dataloader: {}".format(len(valid_dataloader)))
#print("length test dataloader: {}".format(len(test_dataloader)))


# In[37]:


## Exploring the dataloaders
# Iterate over the dataloader
#for batch in test_dataloader:
#    print(batch.keys())
    # Access the data samples in the batch
#    input_ids = batch['input_ids']
#    attention_mask = batch['attention_mask']
#    labels = batch['label']
    
    # Print or inspect the data samples
#    print("Input IDs:", input_ids)
#    print("Attention Mask:", attention_mask)
#    print("Label:", label)
    
    # Additional exploration or analysis of the data
    # ...

    # Break the loop after inspecting one batch if needed
#    break


# ## Testing the model and why we import as AutomModelForSequenceClassification

# >AutoModelForSequenceClassification is a specialized class for sequence classification tasks that includes a pre-built classification head, while AutoModel is a more generic class representing the base model architecture without any task-specific modifications. Choose the appropriate class based on your task requirements and whether you need a pre-configured classification head.

# In[38]:


# Testing the model 
model = AutoModelForSequenceClassification.from_pretrained("michiyasunaga/BioLinkBERT-base", num_labels=len(label2id))
print(model)


# In[39]:


class BIOLINKBERT_BASE(pl.LightningModule):

### __init__
# Model architecture goes in here which in this case is biobert model 
    def __init__(self, num_classes, lr, batch_size):
        super().__init__()
        self.model = AutoModelForSequenceClassification.from_pretrained("michiyasunaga/BioLinkBERT-base", num_labels=num_classes)
        # Multiclass classification loss
        self.criterion = torch.nn.CrossEntropyLoss()
        # Accuracy in every step 
        self.train_acc = torchmetrics.Accuracy(task = 'multiclass', num_classes = num_classes)
        self.val_acc = torchmetrics.Accuracy(task = 'multiclass', num_classes = num_classes)
        self.test_acc = torchmetrics.Accuracy(task = 'multiclass', num_classes = num_classes)
        # Multi class F1 score in every step 
        self.train_f1 = MulticlassF1Score(num_classes = num_classes, average='macro')
        self.val_f1 =  MulticlassF1Score(num_classes = num_classes, average='macro')
        self.test_f1 = MulticlassF1Score(num_classes = num_classes, average='macro')

        self.confmat = ConfusionMatrix(task="multiclass", num_classes=4)
        self.class_names = label2id 
        self.class_conf_labels = class_conf_labels

        self.test_preds_list = []
        self.test_targets_list = []

        self.lr = lr
        self.batch_size = batch_size

### forward 
# Defines the prediction /inference actions

    def forward(self, input_ids, token_type_ids, attention_mask):     
        outputs = self.model(input_ids=input_ids,token_type_ids=token_type_ids, attention_mask=attention_mask)
        return outputs.logits
    
        

### training_step
# The training logic goes in here 
# Use self.log to send any metric to TensorBoard or your preffered logger for visualization and tooling needed for machine learning experimentation
# in self.log(on_epoch= True) add param on_epoch= True to calculate epoch-level metrics
# return loss  or a dictionary of predictions if you want to use them latter in training
    def training_step(self, batch, batch_idx):
        input_ids = batch['input_ids']
        token_type_ids = batch['token_type_ids']
        attention_mask = batch['attention_mask']
        train_labels = batch['label']
        train_logits = self.forward(input_ids=input_ids, token_type_ids=token_type_ids, attention_mask=attention_mask)
        # Quantifies the dissimilarity between the predicted probabilities and the target distribution
        train_loss = self.criterion(train_logits, train_labels)
        # argmax operation is performed along the last dimension of the tensor which is typically the class dimension
        # it returns the indices of the maximum values along the specified dimension in this case, the index of the class with the highest logit value
        train_preds = train_logits.argmax(-1)
        # Log metrics
        self.log("training_loss", train_loss, on_step=True, on_epoch=True, prog_bar=True)
        self.log("training_accuracy", self.train_acc(train_preds, train_labels), on_step=True, on_epoch=True, prog_bar=True)
        self.log("train_f1", self.train_f1(train_preds,train_labels), on_step=True, on_epoch=True, prog_bar=True)
        ####

        return train_loss

### validation_step
# Here goes the validation logic 
# self.log calling it will automatically accumulate and log at the end of the epoch
    def validation_step(self, batch, batch_idx):
        input_ids = batch['input_ids']
        token_type_ids = batch['token_type_ids']
        attention_mask = batch['attention_mask']
        val_labels = batch['label']
        val_logits = self.forward(input_ids=input_ids, token_type_ids=token_type_ids, attention_mask=attention_mask)
        # Getting the predictions 
        val_preds = val_logits.argmax(-1)

        # Calculating metrics 
        val_loss = self.criterion(val_logits, val_labels)
        self.val_acc(val_preds, val_labels)
        self.val_f1(val_preds, val_labels)

        # Log metrics
        self.log("validation_loss", val_loss, on_step=True, on_epoch=True, prog_bar=True)
        self.log("validation_accuracy", self.val_acc, on_step=True, on_epoch=True, prog_bar=True)
        self.log("validation_f1", self.val_f1, on_step=True, on_epoch=True, prog_bar=True)
        
        self.confmat.update(val_preds, val_labels)

        return val_loss
    
    def on_validation_epoch_end(self):
            confmat = self.confmat.compute()
            class_names = self.class_names
            df_cm = pd.DataFrame(confmat.cpu().numpy() , index = [i for i in class_names], columns = [i for i in class_names])
            print('Num of val samples: {}. Check this aligns with the numbers from the dataloader'.format(df_cm.sum(axis=1).sum()))
            #log to wandb
            f, ax = plt.subplots(figsize = (15,10)) 
            sn.heatmap(df_cm, annot=True, ax=ax)
            plt.xlabel("Predicted")
            plt.ylabel("True")
            plt.title("Confusion Matrix - Validation")
            wandb.log({"plot": wandb.Image(f) })
            # For not stacking the results after each epoch 
            self.confmat.reset() 

    def test_step(self, batch, batch_idx):
        #self.test_preds_list = []
        #self.test_targets_list = []
        input_ids = batch['input_ids']
        token_type_ids = batch['token_type_ids']
        attention_mask = batch['attention_mask']
        test_labels = batch['label']
        test_logits = self.forward(input_ids=input_ids, token_type_ids=token_type_ids, attention_mask=attention_mask)
        # Getting the predictions
        test_preds = test_logits.argmax(-1)
        # Calculating metrics
        test_loss = self.criterion(test_logits, test_labels)
        self.test_acc(test_preds, test_labels)
        self.test_f1(test_preds,test_labels)
        # Log metrics
        self.log("test_loss", test_loss, on_step=True, on_epoch=True, prog_bar=True)
        self.log("test_accuracy", self.test_acc, on_step=True, on_epoch=True, prog_bar=True)   
        self.log("test_f1", self.test_f1, on_step=True, on_epoch=True, prog_bar=True)

        self.test_preds_list.extend(test_preds.cpu().detach().numpy())
        self.test_targets_list.extend(test_labels.cpu().detach().numpy())
        return test_loss
    
    def on_test_epoch_end(self):
        wandb.log({"confusion_matrix-test":wandb.plot.confusion_matrix(probs=None, y_true= self.test_targets_list, preds = self.test_preds_list, class_names=self.class_conf_labels)})

### configure_optimizers
# optimizers go in here
# optimizers assist in minimizing the loss function, it updates the model in response to the output of the loss function
# self.parameters() will contain parameters for encoder and decoder
# AdamW Adaptive Moment Estimation
    def configure_optimizers(self):
        optimizer = AdamW(self.parameters(), lr=self.lr)
        return optimizer

    def train_dataloader(self):
        # We will use 10,16,32 and 64
        train_dataloader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)
        return train_dataloader

    def val_dataloader(self):
        valid_dataloader = DataLoader(valid_dataset, batch_size=self.batch_size)
        return valid_dataloader

    def test_dataloader(self):
        test_dataloader = DataLoader(test_dataset, batch_size=self.batch_size)
        return test_dataloader


# ## Train the model 

# In[40]:


wandb.login()


# # Hyperparameter search

# In[47]:


# Defining sweep configuration 
sweep_config = {
    "name": "biolinkbert_sweep",
    # iterate over every combination of values
    "method" : "grid",
    # optional for a grid but good practice
    "metric": {
        "name": "validation_loss",
        "goal": "minimize"
    },
    "parameters": {
        "lr" : {
            # 1e-5, 3e-5, 5e-5
            "values": [0.00001, 0.00003, 0.00005]
        }, 
        "batch_size": {
            "values": [10, 16, 32, 64] 
        }
    }

}


# In[48]:


# Creating a sweep id based on our configuration 
sweep_id = wandb.sweep(sweep_config, project="deep_for_bio_nlp")


# ## Running an agent

# In[49]:


def sweep_iteration():
    wandb.init()
    wandb_logger = WandbLogger(name='biolinkbert_base_v2', project='deep_for_bio_nlp')
# for early stopping, see https://pytorch-lightning.readthedocs.io/en/1.0.0/early_stopping.html?highlight=early%20stopping
    early_stop_callback = EarlyStopping(
        monitor='val_loss',
        patience=2,
        strict=False,
        verbose=False,
        mode='min'
        )
    model = BIOLINKBERT_BASE(num_classes=len(label2id),lr=wandb.config.lr,batch_size=wandb.config.batch_size)
    # For local test running
#    trainer = Trainer(logger=wandb_logger, accelerator= 'cpu',devices= 1, max_epochs = 1)
    # For Ascend server running 
    trainer = Trainer(logger=wandb_logger, accelerator= 'auto',devices= 'auto', callbacks=[EarlyStopping(monitor='val_loss')])
    # Enable the following Trainer arguments to run on Apple silicon gpus (MPS devices).
    # The MPSAccelerator only supports 1 device at a time. Currently there are no machines with multiple MPS-capable GPUs.
    # params to run on mac but bugging 
    #trainer = Trainer(logger=wandb_logger, accelerator= 'mps',devices= 1, callbacks=[EarlyStopping(monitor='validation_loss')])
    # original trainer params to run local 
    #trainer = Trainer(logger=wandb_logger, accelerator= 'cpu',devices= 1, callbacks=[EarlyStopping(monitor='validation_loss')])
    trainer.fit(model)


# In[50]:


wandb.agent(sweep_id, function=sweep_iteration)


# In[ ]:


#wandb_logger = WandbLogger(name='biolinkbert_base_v2', project='deep_for_bio_nlp')
# for early stopping, see https://pytorch-lightning.readthedocs.io/en/1.0.0/early_stopping.html?highlight=early%20stopping
#early_stop_callback = EarlyStopping(
#    monitor='val_loss',
#    patience=2,
#    strict=False,
#    verbose=False,
#    mode='min'
#)
#model = BIOLINKBERT_BASE(num_classes=len(label2id))
# For local test running
#trainer = Trainer(logger=wandb_logger, accelerator= 'cpu',devices= 1, max_epochs = 2)
# For Ascend server running 
#trainer = Trainer(logger=wandb_logger, accelerator= 'auto',devices= 'auto', callbacks=[EarlyStopping(monitor='validation_loss')])
# Enable the following Trainer arguments to run on Apple silicon gpus (MPS devices).
# The MPSAccelerator only supports 1 device at a time. Currently there are no machines with multiple MPS-capable GPUs.
# params to run on mac but bugging 
#trainer = Trainer(logger=wandb_logger, accelerator= 'mps',devices= 1, callbacks=[EarlyStopping(monitor='validation_loss')])


#trainer.fit(model)


# In[ ]:


#trainer.test()

