import torch as th
import torch.nn as nn
import torch.nn.functional as F


class MLPCritic(nn.Module):
    def __init__(self, input_shape, output_shape, args):
        super(MLPCritic, self).__init__()
        self.args = args

        # Easiest to reuse hid_size variable
        self.fc1 = nn.Linear(input_shape, args.hid_size)
        if args.layernorm:
            self.layernorm = nn.LayerNorm(args.hid_size)
        self.fc2 = nn.Linear(args.hid_size, args.hid_size)
        self.fc3 = nn.Linear(args.hid_size, output_shape)

    def init_hidden(self):
        # make hidden states on same device as model
        return self.fc1.weight.new(1, self.args.hid_size).zero_()

    def forward(self, inputs, hidden_state):
        x = self.fc1(inputs)
        if self.args.layernorm:
            x = self.layernorm(x)
        x = F.relu(x)
        h = F.relu(self.fc2(x))
        v = self.fc3(h)
        return v, h