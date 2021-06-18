import torch as th
import torch.nn as nn
import torch.nn.functional as F



class RNNCritic(nn.Module):
    def __init__(self, input_shape, output_shape, args):
        super(RNNCritic, self).__init__()
        self.args = args

        self.fc1 = nn.Linear(input_shape, args.hid_size)
        if args.layernorm:
            self.layernorm = nn.LayerNorm(args.hid_size)
        self.rnn = nn.GRUCell(args.hid_size, args.hid_size)
        self.fc2 = nn.Linear(args.hid_size, output_shape)

    def init_hidden(self):
        # make hidden states on same device as model
        return self.fc1.weight.new(1, self.args.hid_size).zero_()

    def forward(self, inputs, hidden_state):
        x = self.fc1(inputs)
        if self.args.layernorm:
            x = self.layernorm(x)
        x = F.relu()
        h_in = hidden_state.reshape(-1, self.args.hid_size)
        h = self.rnn(x, h_in)
        v = self.fc2(h)
        return v, h