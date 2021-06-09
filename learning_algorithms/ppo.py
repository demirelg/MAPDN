from learning_algorithms.rl_algorithms import ReinforcementLearning
from utilities.util import select_action, cuda_wrapper, batchnorm, normal_log_density, multinomials_log_density
import torch


class PPO(ReinforcementLearning):
    def __init__(self, args):
        super(PPO, self).__init__('PPO', args)

    def __call__(self, batch, behaviour_net, target_net):
        return self.get_loss(batch, behaviour_net, target_net)

    def get_loss(self, batch, behaviour_net, target_net):
        batch_size = len(batch.state)
        state, actions, old_log_prob_a, old_values, old_next_values, rewards, next_state, done, last_step, actions_avail = behaviour_net.unpack_data(batch)
        old_values = old_values.squeeze(-1)
        old_next_values = old_next_values.squeeze(-1)
        if self.args.continuous:
            means, log_stds, _ = behaviour_net.policy(state)
            if means.size(-1) > 1:
                means_ = means.sum(dim=1, keepdim=True)
                log_stds_ = log_stds.sum(dim=1, keepdim=True)
            else:
                means_ = means
                log_stds_ = log_stds
            action_out = (means, log_stds)
            log_prob_a = normal_log_density(actions, means_, log_stds_)
            restore_mask = 1. - cuda_wrapper((actions_avail == 0).float(), self.cuda_)
            log_prob_a = (restore_mask * log_prob_a).sum(dim=-1)
            old_log_prob_a = (restore_mask * old_log_prob_a).sum(dim=-1)
        else:
            logits, _ = behaviour_net.policy(state)
            logits[actions_avail == 0] = -9999999
            action_out = logits
            log_prob_a = multinomials_log_density(actions, logits)
        ratios = torch.exp(log_prob_a.squeeze(-1) - old_log_prob_a.squeeze(-1).detach())
        values = behaviour_net.value(state, None).contiguous().view(-1, behaviour_net.n_)
        next_values = behaviour_net.value(next_state, None).contiguous().view(-1, behaviour_net.n_)
        advantages = cuda_wrapper(torch.zeros((batch_size, behaviour_net.n_), dtype=torch.float), behaviour_net.cuda_)
        returns = cuda_wrapper(torch.zeros((batch_size, behaviour_net.n_), dtype=torch.float), behaviour_net.cuda_)
        assert advantages.size() == values.size() == returns.size()
        # GAE -> advantage
        last_advantages = 0
        for i in reversed(range(rewards.size(0))):
            if last_step[i]:
                mask = 1.0 - done[i]
            else:
                mask = 1.0
            deltas_ = rewards[i] + behaviour_net.args.gamma * old_next_values[i].detach() * mask - old_values[i]
            last_advantages = deltas_ + behaviour_net.args.gamma * behaviour_net.args.lambda_ * last_advantages * mask
            advantages[i] = last_advantages
        next_return = next_values[-1].detach()
        for i in reversed(range(rewards.size(0))):
            if last_step[i]:
                next_return = 0 if done[i] else next_values[i].detach()
            returns[i] = rewards[i] + behaviour_net.args.gamma * next_return
            next_return = returns[i]
        # normalise advantage
        if behaviour_net.args.normalize_advantages:
            advantages = batchnorm(advantages)
        # policy loss
        assert ratios.size() == advantages.size()
        surr1 = ratios * advantages.detach()
        surr2 = torch.clamp(ratios, 1 - behaviour_net.args.eps_clip, 1 + behaviour_net.args.eps_clip) * advantages.detach()
        # policy_loss = - torch.min(surr1, surr2).mean(dim=0)
        policy_loss = - torch.min(surr1, surr2).mean()
        # value loss
        assert old_values.size() == values.size()
        values_clipped = old_values + torch.clamp(values - old_values, - behaviour_net.args.eps_clip, behaviour_net.args.eps_clip)
        surr1 = (values - returns).pow(2)
        surr2 = (values_clipped - returns).pow(2)
        # value_loss = self.args.value_loss_coef * torch.max(surr1, surr2).mean(dim=0)
        value_loss = self.args.value_loss_coef * torch.max(surr1, surr2).mean()
        return policy_loss, value_loss, action_out