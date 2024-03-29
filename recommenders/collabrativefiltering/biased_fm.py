from evaluation.evaluation import *
from display.training_process import *
import pickle
import logging
import logging.handlers
import copy

class BiasedFM():
    def __init__(self, path, parameters):

        self.user_index_dict = pickle.load(open(path[:-1] + 'uiDict', 'rb'))
        self.item_index_dict = pickle.load(open(path[:-1] + 'iiDict', 'rb'))
        self.train_data = pd.read_csv(path + 'eccTrainData')
        self.user_purchased_item_dict = pickle.load(open(path + 'upiTrainDict', 'rb'))
        self.item_purchased_user_dict = pickle.load(open(path + 'ipuTrainDict', 'rb'))
        self.user_item_rating_dict = pickle.load(open(path + 'uiraTrainDict', 'rb'))

        self.true_rating_dict = pickle.load(open(path + 'uiraTestDict', 'rb'))
        self.true_purchased_dict = pickle.load(open(path + 'upiTestDict', 'rb'))

        self.user_count = len(self.user_index_dict.keys())
        self.item_count = len(self.item_index_dict.keys())


        self.factors = parameters['factors']
        self.learning_rate = parameters['learningrate']
        self.user_regular = parameters['userregular']
        self.item_regular = parameters['itemregular']
        self.iter = parameters['iter']
        self.TopN = parameters['n']
        self.recommend_new = parameters['recommend_new']
        self.insights = parameters['display']

        self.figure_data = []
        logging.config.fileConfig('log_conf')
        self.biasedFM_logger = logging.getLogger('biasedFM')
        self.biasedFM_logger.info('Factors: '+str(self.factors) +' learningrate: '+ str(self.learning_rate)+
                                  ' userregular: '+str(self.user_regular) + ' itemregular: '+str(self.item_regular)+
                                  ' iter:' + str(self.iter)+' TopN:' + str(self.TopN))

    def fit(self):
        self.mu = np.array([r for (ui, r) in self.user_item_rating_dict.items()]).mean()
        self.bu = np.zeros(self.user_count)
        self.bi = np.zeros(self.item_count)
        temp = math.sqrt(self.factors)
        self.pu = np.array([np.array([(0.1 * random.random() / temp) for j in range(self.factors)]) for i in range(self.user_count)])
        self.qi = np.array([np.array([(0.1 * random.random() / temp) for j in range(self.factors)]) for i in range(self.item_count)])

        self.pre_loss = float('Inf')
        self.figure_data.append([np.zeros(self.user_count),np.zeros(self.user_count),np.zeros(self.user_count),
                                 0, copy.deepcopy(self.pu),copy.deepcopy(self.qi),copy.deepcopy(self.bu),copy.deepcopy(self.bi)])

        for step in range(self.iter):
            self.biasedFM_logger.info('iteration: ' + str(step))
            for (ui, r) in self.user_item_rating_dict.items():
                user = int(ui.split('##')[0])
                item = int(ui.split('##')[1])
                eui = r - self.predict(user, item)
                self.bu[user] += self.learning_rate*(eui-self.user_regular*self.bu[user])
                self.bi[item] += self.learning_rate*(eui-self.item_regular*self.bi[item])
                temp = self.qi[item]
                self.qi[item] += self.learning_rate*(np.dot(eui, self.pu[user]) - np.dot(self.item_regular, self.qi[item]))
                self.pu[user] += self.learning_rate*(np.dot(eui, temp) - np.dot(self.user_regular, self.pu[user]))

            current_loss = self.score(1)[1]
            if current_loss > self.pre_loss:
                self.biasedFM_logger.info('training end.')
                break
            else:
                self.pre_loss = current_loss
                self.learning_rate = self.learning_rate * 0.93

        if self.insights:
            d = TrainingProcess(self.figure_data)
            d.run()

    def save(self):
        t = pd.DataFrame([self.mu])
        t.to_csv('../results/biased_fm_mu')
        t = pd.DataFrame(self.pu)
        t.to_csv('../results/biased_fm_pu')
        t = pd.DataFrame(self.qi)
        t.to_csv('../results/biased_fm_qi')
        t = pd.DataFrame(self.bu)
        t.to_csv('../results/biased_fm_bu')
        t = pd.DataFrame(self.bi)
        t.to_csv('../results/biased_fm_bi')
        t = pd.DataFrame(self.user_recommend)
        t.to_csv('../results/biased_fm_user_recommend')


    def predict(self, user, item):
        ans = self.mu + self.bi[item] + self.bu[user] + np.dot(self.qi[item], self.pu[user])
        if ans > 5:
            return 5
        elif ans < 1:
            return 1
        return ans

    def recommend(self, u):
        if self.recommend_new == 0:
            candidate = np.array([self.predict(u, i) for i in range(self.item_count)])
        else:
            candidate = np.array([self.predict(u, i) for i in range(self.item_count) if i not in self.user_purchased_item_dict[u]])

        result = np.argsort(candidate)[-1:-self.TopN-1:-1]
        return result

    def score(self, log):
        current_loss = 0.0
        for (ui, r) in self.user_item_rating_dict.items():
            user = int(ui.split('##')[0])
            item = int(ui.split('##')[1])
            eui = r - self.predict(user, item)
            current_loss += eui**2
        for user in self.user_index_dict.values():
            user = int(user)
            current_loss += self.user_regular*(np.dot(self.pu[user], self.pu[user])+self.bu[user]**2)
        for item in self.item_index_dict.values():
            item = int(item)
            current_loss += self.item_regular*(np.dot(self.qi[item], self.qi[item])+self.bi[item]**2)

        e = Eval()
        predict_rating_list = []
        true_rating_list = []
        predict_top_n = []
        true_purchased = []
        self.user_recommend = []

        for (ui, rating) in self.true_rating_dict.items():
            user = int(ui.split('##')[0])
            item = int(ui.split('##')[1])
            predict_rating_list.append(self.predict(user, item))
            true_rating_list.append(rating)

        for (u, items) in self.true_purchased_dict.items():
            recommended_item = self.recommend(u)
            predict_top_n.append(recommended_item)
            self.user_recommend.append([u, recommended_item])
            true_purchased.append(items)


        rmse = e.RMSE(predict_rating_list, true_rating_list)
        f1, hit_ratio, ndcg, p, r, f = e.evalAll(predict_top_n, true_purchased)
        if log:
            self.biasedFM_logger.info('training loss: ' + str(current_loss) + ',  test RMSE: ' + str(rmse))
        self.figure_data.append([np.array(p), np.array(r), np.array(f), rmse, copy.deepcopy(self.pu), copy.deepcopy(self.qi), copy.deepcopy(self.bu),copy.deepcopy(self.bi)])
        return [rmse, current_loss, f1, hit_ratio, ndcg, p, r, f]







