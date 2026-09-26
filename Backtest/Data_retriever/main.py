from src import logger
from src.components.fyers_login import fyers_login
from src.components.data_retrieval import DataRetrieval

def login():
    STAGE="login Stage"
    try:
        logger.info(f"-----{STAGE}-----")
        login=fyers_login.login()
        logger.info(f"{STAGE} sucessful")
    except Exception as e:
        logger.exception(e)
        raise e
    

def user_data_retiver():
    STAGE="user information- Stage"
    try:
        logger.info(f"-----{STAGE}-----")
        data=DataRetrieval()
        data.userdata()
        data.hist_data()
        logger.info(f"{STAGE} sucessful")
    except Exception as e:
        logger.exception(e)
        raise e
    





if __name__=="__main__":
    login()
    user_data_retiver()

