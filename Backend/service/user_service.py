import bcrypt
import jwt
import pandas as pd
import numpy as np
import boto3
import uuid

from config           import SECRET, ALGORITHM
from utils.validate   import (password_validate,
                              phone_number_validate)
from utils.exceptions import (PasswordValidationError,
                              PhoneNumberValidationError,
                              ExistError,
                              NotExistError,
                              NotMatchError,
                              DeleteSellerError,
                              NotSupportImageFormat,
                              InvalidUserError
                              )


class UserService:
    def __init__(self, user_dao, config):
        self.user_dao = user_dao
        self.config   = config
        self.s3       = boto3.client(
            's3',
            aws_access_key_id     = config.AWS_ACCESS_KEY,
            aws_secret_access_key = config.AWS_SECRET_ACCESS_KEY
        )

    # 회원가입
    def sign_up_account(self, user_data, conn):
        # 유저 정보 찾기
        get_user = self.user_dao.get_user(user_data, conn)
        # 유저 정보가 없으면 가입 시킨다.
        if get_user is None:
            # 각종 validate 처리와 오류 발생
            if password_validate(user_data.get('password')):
                raise PasswordValidationError('비밀번호는 8~20글자의 영문대소문자, 숫자, 특수문자를 조합해야 합니다.', 400)
            elif phone_number_validate(user_data.get('owner_number')):
                raise PhoneNumberValidationError('올바른 전화번호를 입력하세요.', 400)
            elif (user_data.get('password')) != (user_data.get('confirm_password')):
                raise NotMatchError('비밀번호가 일치하지 않습니다.', 400)
            # validate 통과 후 회원가입
            else:
                hashed_password = bcrypt.hashpw(user_data.get('password').encode('utf-8'), bcrypt.gensalt())
                decoded_password = hashed_password.decode('utf-8')
                user_data['password'] = decoded_password
                sign_up_result = self.user_dao.sign_up_account(user_data, conn)
                return sign_up_result
        # 유저 정보가 있으면 오류 발생
        else:
            if get_user['user_id'] == user_data['user_id']:
                raise ExistError('이미 존재하는 아이디입니다.', 409)

    # 로그인
    def sign_in_seller(self, user_data, conn):
        # 유저 정보 찾기
        get_seller_info = self.user_dao.get_seller_info(user_data, conn)
        # 유저 정보가 없으면 오류 발생
        if get_seller_info is None:
            raise NotExistError('존재하지 않는 회원입니다.', 400)
        elif get_seller_info.get('is_deleted') == 1:
            raise NotExistError('탈퇴한 회원입니다.', 400)
        # 유저 정보가 존재한다면 저장된 비밀번호와 비교 후 로그인, 토큰 전달
        elif bcrypt.checkpw(user_data.get('password').encode('utf-8'), get_seller_info.get('password').encode('utf-8')):
            access_token = jwt.encode({'id': get_seller_info['account_id']}, SECRET['secret'], ALGORITHM['algorithm'])
            decoded_token = access_token.decode('utf-8')
            return {'message': 'SUCCESS!', 'token': decoded_token}, 200
        else:
            raise NotMatchError('아이디와 비밀번호를 다시 확인해주세요.', 400)

    def get_seller_list(self, filter_data, conn):
        # account = self.user_dao.get_account_info({'id': g.user}, conn)

        # if account['class_id'] == 2:
        #     raise InvalidUserError('권한이 없는 사용자입니다.', 403)

        seller_list = self.user_dao.get_seller_list(filter_data, conn)
        # print(seller_list['seller_action_id'])
        # print(seller_list['seller_action'])
        columns = [
            {
                'title': '번호',
                'dataIndex': 'id'
            },
            {
                'title': '셀러아이디',
                'dataIndex': 'seller_id'
            },
            {
                'title': '영문이름',
                'dataIndex': 'eng_name'
            },
            {
                'title': '한글이름',
                'dataIndex': 'kor_name',
            },
            {
                'title': '담당자이름',
                'dataIndex': 'owner_name'
            },
            {
                'title': '셀러상태',
                'dataIndex': 'seller_status'
            },
            {
                'title': '담당자연락처',
                'dataIndex': 'phone_number'
            },
            {
                'title': '담당자이메일',
                'dataIndex': 'email'
            },
            {
                'title': '셀러속성',
                'dataIndex': 'seller_attribute'
            },
            {
                'title': '등록일시',
                'dataIndex': 'created_at'
            },
            {
                'title': 'Actions',
                'dataIndex': 'seller_actions'
            }
        ]

        data = {
            'columns': columns,
            'seller_count': self.user_dao.get_seller_count(filter_data, conn)['count'],
            'data': [{
                'id'               : seller['id'],
                'seller_id'        : seller['seller_id'],
                'eng_name'         : seller['eng_name'],
                'kor_name'         : seller['kor_name'],
                'seller_status'    : seller['seller_status'],
                'seller_attribute' : seller['seller_attribute'],
                'owner_name'       : seller['owner_name'],
                'phone_number'     : seller['phone_number'],
                'email'            : seller['email'],
                'created_at'       : seller['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'seller_actions'   : sorted([{
                    'id'  : seller_action_id,
                    'name': seller_action
                } for seller_action_id, seller_action in
                    zip(seller['seller_action_id'].split(','), seller['seller_action'].split(','))],
                    key=lambda seller_action:seller_action['id'])
                if seller['seller_action_id'] else None
            } for seller in seller_list]
        }

        return data

    def create_excel_seller_info(self, seller_info):
        columns = [
            '셀러번호',
            '관리자계정ID',
            '셀러영문명',
            '셀러한글명',
            '담당자명',
            '담당자연락처',
            '담당자이메일',
            '셀러속성',
            '셀러등록일',
            '승인여부'
        ]

        seller_list = [
            [
                seller['id'],
                seller['seller_id'],
                seller['eng_name'],
                seller['kor_name'],
                seller['seller_attribute'],
                seller['owner_name'],
                seller['phone_number'],
                seller['email'],
                seller['created_at'],
                seller['seller_status']
            ] for seller in seller_info['data']]

        data_frame = pd.DataFrame(np.array(seller_list), columns=columns)

        return data_frame

    def get_seller_status(self, conn):
        seller_status = self.user_dao.get_seller_status(conn)

        return seller_status

    def get_seller_attributes(self, conn):
        seller_attributes = self.user_dao.get_seller_attributes(conn)

        return seller_attributes

    def update_seller_status(self, modifier_id, account_info, conn):
        if 'id' not in account_info:
            raise KeyError

        if 'seller_action_id' not in account_info:
            raise KeyError

        if len(account_info) != 2:
            raise KeyError

        account_info['modifier_id'] = modifier_id

        previous_seller_info = self.user_dao.get_seller(account_info, conn)

        if previous_seller_info['is_deleted']:
            raise DeleteSellerError('삭제된 셀러 입니다.', 400)

        seller_status = self.user_dao.get_seller_action_to_status(account_info, conn)

        if seller_status['seller_status_id'] is None:
            account_info['is_deleted'] = 1
        else:
            account_info['seller_status_id'] = seller_status['seller_status_id']

        now = self.user_dao.get_now_time(conn)
        previous_seller_info['now'] = now['now']

        account_info = dict(previous_seller_info, **account_info)

        self.user_dao.insert_seller_info(account_info, conn)
        updated_seller = self.user_dao.update_seller_info(previous_seller_info, conn)

        return updated_seller

    def get_seller_info(self, account_info, conn):
        found_seller_info = self.user_dao.get_seller(account_info, conn)

        seller_info = {
            'seller_profile'      : found_seller_info['seller_profile'],
            'seller_status_id'    : found_seller_info['seller_status_id'],
            'seller_attribute_id' : found_seller_info['seller_attribute_id'],
            'kor_name'            : found_seller_info['name'],
            'eng_name'            : found_seller_info['eng_name'],
            'seller_id'           : found_seller_info['seller_id'],
            'seller_background'   : found_seller_info['seller_background'],
            'seller_intro'        : found_seller_info['seller_intro'],
            'seller_detail'       : found_seller_info['seller_detail'],
            'owner_name'          : found_seller_info['owner_name'],
            'owner_number'        : found_seller_info['owner_number'],
            'owner_email'         : found_seller_info['owner_email'],
            'cs_number'           : found_seller_info['cs_number'],
            'zipcode'             : found_seller_info['zipcode'],
            'first_address'       : found_seller_info['first_address'],
            'last_address'        : found_seller_info['last_address'],
            'open_time'           : str(found_seller_info['open_time']),
            'close_time'          : str(found_seller_info['close_time']),
            'delivery'            : found_seller_info['delivery'],
            'refund'              : found_seller_info['refund'],
        }

        return seller_info

    def update_seller_info(self, seller_info, seller_image, conn):

        previous_seller_info = self.user_dao.get_seller(seller_info, conn)

        if previous_seller_info['is_deleted']:
            raise DeleteSellerError('삭제된 셀러 입니다.', 400)

        now = self.user_dao.get_now_time(conn)
        now = now['now']
        previous_seller_info['now'] = now
        seller_info['now'] = now

        allowed_extensions = ['image/jpg', 'image/jpeg', 'image/png']

        seller_profile = seller_image['seller_profile_image']
        seller_background = seller_image['seller_background_image']

        profile_image_extension = seller_profile.content_type
        background_image_extension = seller_background.content_type

        if profile_image_extension not in allowed_extensions:
            raise NotSupportImageFormat('지원하지 않는 이미지 형식입니다. 셀러 프로필 이미지를 확인하세요.', 400)

        if background_image_extension not in allowed_extensions:
            raise NotSupportImageFormat('지원하지 않는 이미지 형식입니다. 셀러 배경 이미지를 확인하세요.', 400)

        profile_image_uuid = str(uuid.uuid1())
        background_image_uuid = str(uuid.uuid1())

        seller_profile_image_url = f'seller/{now.year}' \
                                   f'/{now.month}' \
                                   f'/{now.day}' \
                                   f'/{previous_seller_info["seller_id"]}_profile_{profile_image_uuid}'

        seller_background_image_url = f'seller/{now.year}' \
                                      f'/{now.month}' \
                                      f'/{now.day}' \
                                      f'/{previous_seller_info["seller_id"]}_background_{background_image_uuid}'

        self.s3.put_object(
            Body=seller_profile,
            Bucket='brandistorage',
            Key=seller_profile_image_url,
            ContentType=profile_image_extension
        )

        self.s3.put_object(
            Body=seller_background,
            Bucket='brandistorage',
            Key=seller_background_image_url,
            ContentType=background_image_extension
        )

        s3_bucket_url = "https://brandistorage.s3.ap-northeast-2.amazonaws.com/"
        seller_info['seller_profile'] = s3_bucket_url + seller_profile_image_url
        seller_info['seller_background'] = s3_bucket_url + seller_background_image_url

        seller_info = dict(previous_seller_info, **seller_info)

        self.user_dao.insert_seller_info(seller_info, conn)

        updated_seller = self.user_dao.update_seller_info(previous_seller_info, conn)

        return updated_seller
    
    # NOTE soomyung's API get seller data
    def get_filtered_sellers(self, filter_data, conn):
        
        if "user_id" not in filter_data:
            raise KeyError
        filter_data['user_id'] = '%' + filter_data['user_id'] + '%'
        print(filter_data['user_id'])
        filtered_sellers =  self.user_dao.get_filtered_sellers(filter_data, conn)
        
        return filtered_sellers
