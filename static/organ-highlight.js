/**
 * Organ Highlighting System
 * Detects mentioned organs in radiology reports and highlights available anatomy images
 */

(function() {
  'use strict';

  // Available anatomy images
  const AVAILABLE_ORGANS = {
    'brain': '/static/images/anatomy/brain.svg',
    'heart': '/static/images/anatomy/heart.svg',
    'lungs': '/static/images/anatomy/lungs.svg',
    'lung': '/static/images/anatomy/lungs.svg',
    'liver': '/static/images/anatomy/liver.svg',
    'kidney': '/static/images/anatomy/kidney.svg',
    'kidneys': '/static/images/anatomy/kidney.svg',
    'stomach': '/static/images/anatomy/stomach.svg'
  };

  // Organ detection keywords (expanded)
  const ORGAN_KEYWORDS = {
    'brain': ['brain', 'cerebral', 'intracranial', 'head ct', 'cranial', 'skull', 'cerebrum', 'cerebellum'],
    'heart': ['heart', 'cardiac', 'coronary', 'myocardial', 'pericardial', 'atrial', 'ventricular'],
    'lungs': ['lung', 'pulmonary', 'pleural', 'bronchial', 'thorax', 'chest', 'respiratory'],
    'liver': ['liver', 'hepatic', 'hepatobiliary'],
    'kidney': ['kidney', 'renal', 'nephro', 'ureter'],
    'stomach': ['stomach', 'gastric', 'gastrointestinal', 'abdominal']
  };

  // Medical condition detection with example image URLs
  const CONDITION_EXAMPLES = {
    'kidney stone': {
      keywords: ['kidney stone', 'renal stone', 'nephrolithiasis', 'calculus', 'calculi', 'renal calculi'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/24804/1af425ddaf16fa001b5d129ec2ecbb_big_gallery.jpeg',
      altText: 'Example CT scan showing kidney stones',
      description: 'Kidney stones appear as bright white spots on CT scans due to calcium content'
    },
    'pleural effusion': {
      keywords: ['pleural effusion', 'fluid in lung', 'pleural fluid', 'effusion'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/53183623/f69b9ba15aa08e02024c4dc168ab80aa0dfc09c8bde1662cd7ce62d13c7b016d_big_gallery.jpeg',
      altText: 'Example chest X-ray showing pleural effusion',
      description: 'Pleural effusion shows as fluid collection blunting the costophrenic angle'
    },
    'pneumonia': {
      keywords: ['pneumonia', 'consolidation', 'infiltrate', 'opacity', 'lung infection'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/8151527/95a07767cebe3da2923819c650a539_big_gallery.jpg',
      altText: 'Example chest X-ray showing pneumonia',
      description: 'Pneumonia appears as cloudy white areas (consolidation) in the affected lung'
    },
    'fracture': {
      keywords: ['fracture', 'broken', 'break', 'crack', 'fx'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/6/67/Colles-fracture.jpg',
      altText: 'Example X-ray showing bone fracture',
      description: 'Fractures appear as dark lines or breaks disrupting the bone cortex'
    },
    'enlarged heart': {
      keywords: ['cardiomegaly', 'enlarged heart', 'heart enlargement', 'cardiac enlargement'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/604505/8d2027dc816cf6bea4ced88ff487cbef1636da2890b7c558846da148431559c9_big_gallery.jpeg',
      altText: 'Example chest X-ray showing enlarged heart',
      description: 'Enlarged heart appears with cardiothoracic ratio greater than 50% on PA chest X-ray'
    },
    'brain tumor': {
      keywords: ['brain tumor', 'brain mass', 'intracranial mass', 'cerebral mass', 'brain lesion', 'glioma', 'meningioma'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/5/5f/Hirnmetastase_MRT-T1_KM.jpg',
      altText: 'Example brain MRI showing abnormal mass',
      description: 'Brain masses appear as abnormal areas with contrast enhancement on MRI'
    },
    'stroke': {
      keywords: ['stroke', 'infarct', 'ischemic', 'cva', 'cerebrovascular accident'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/139045/ac57c1be30d13d1c89b8b65d693a03_big_gallery.jpg',
      altText: 'Example CT showing ischemic stroke',
      description: 'Ischemic stroke appears as dark areas representing dead brain tissue'
    },
    'brain hemorrhage': {
      keywords: ['hemorrhage', 'bleed', 'bleeding', 'intracranial hemorrhage', 'ich', 'subdural', 'epidural'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/66455109/8de8e96b667f7f07b0c4e488ea78d219d613270c0b95e7f614e1370af9d9f37f_big_gallery.jpeg',
      altText: 'Example CT showing brain hemorrhage',
      description: 'Brain hemorrhage appears as bright white areas on CT scan'
    },
    'pulmonary edema': {
      keywords: ['pulmonary edema', 'lung edema', 'fluid in lungs', 'pulmonary congestion'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/1429771/ef3a23eddf31faee980a4011d9d5ee_big_gallery.jpg',
      altText: 'Example chest X-ray showing pulmonary edema',
      description: 'Pulmonary edema appears as bat-wing pattern or widespread bilateral infiltrates'
    },
    'liver cyst': {
      keywords: ['liver cyst', 'hepatic cyst', 'cyst in liver'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/1263816/32122190a29e1efb176daf65a21848_gallery.jpg',
      altText: 'Example ultrasound showing liver cyst',
      description: 'Liver cysts appear as dark, round, well-defined fluid-filled structures'
    },
    'appendicitis': {
      keywords: ['appendicitis', 'inflamed appendix', 'appendix'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/42276667/2c041670eb0bc608fcfa35194f721c_gallery.jpeg',
      altText: 'Example CT showing appendicitis',
      description: 'Appendicitis shows as enlarged, thickened appendix with surrounding inflammation'
    },
    'pulmonary embolism': {
      keywords: ['pulmonary embolism', 'pe', 'blood clot', 'clot in lung', 'embolus'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/59632221/419fb0cc39742cfe12fdfc53c07b5f9a2c2011d379ec576401f59942ed7f7d34_big_gallery.jpeg',
      altText: 'Example CT angiogram showing pulmonary embolism',
      description: 'Pulmonary embolism appears as dark filling defect in contrast-filled pulmonary artery'
    },
    'aortic aneurysm': {
      keywords: ['aneurysm', 'aortic aneurysm', 'dilated aorta', 'aaa', 'abdominal aortic aneurysm'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/537896/193227405d7bc7093cf287f4045b25_big_gallery.jpg',
      altText: 'Example CT showing aortic aneurysm',
      description: 'Aortic aneurysm appears as abnormal widening of the aorta (>3cm diameter)'
    },
    'pneumothorax': {
      keywords: ['pneumothorax', 'collapsed lung', 'air in pleural space'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/25371812/245d5e88c4b42c42b62ba9b703c4cc_big_gallery.jpeg',
      altText: 'Example chest X-ray showing pneumothorax',
      description: 'Pneumothorax appears as dark air space between lung and chest wall with visible lung edge'
    },
    'gallstones': {
      keywords: ['gallstone', 'cholelithiasis', 'gallbladder stone'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/34413824/downloaded_image20240312-12155-5m90dh_gallery.jpeg',
      altText: 'Example ultrasound showing gallstones',
      description: 'Gallstones appear as bright echogenic foci with posterior acoustic shadowing on ultrasound'
    },
    'spinal stenosis': {
      keywords: ['spinal stenosis', 'stenosis', 'narrowing', 'canal narrowing'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/c/c2/Spinal_stenosis.jpg',
      altText: 'Example MRI showing spinal stenosis',
      description: 'Spinal stenosis shows as narrowing of the spinal canal compressing nerve structures'
    },
    'herniated disc': {
      keywords: ['herniated disc', 'disc herniation', 'bulging disc', 'slipped disc', 'prolapsed disc'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/12738056/076a23012e343a4b8e7452e3dc0b0a_big_gallery.jpg',
      altText: 'Example MRI showing herniated disc',
      description: 'Herniated disc appears as disc material protruding beyond normal vertebral boundaries'
    },
    'tumor': {
      keywords: ['tumor', 'mass', 'neoplasm', 'growth', 'lesion'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/a/a3/Lung_cancer.png',
      altText: 'Example CT showing tumor/mass',
      description: 'Tumors appear as abnormal tissue masses with variable density and enhancement patterns'
    },
    'lymphoma': {
      keywords: ['lymphoma', 'lymph node', 'lymphadenopathy', 'enlarged lymph nodes'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/22328/964f22cc285ef868d5d5cf2ebedf05_big_gallery.jpeg',
      altText: 'Example CT showing lymphadenopathy',
      description: 'Lymphoma shows as enlarged lymph nodes (>1cm) in multiple regions'
    },
    'osteoarthritis': {
      keywords: ['osteoarthritis', 'arthritis', 'degenerative', 'joint space narrowing', 'osteophyte'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/135647/2eeee0a3ef1b6191d8a0684218e676_big_gallery.jpg',
      altText: 'Example X-ray showing osteoarthritis',
      description: 'Osteoarthritis shows joint space narrowing, bone spurs (osteophytes), and sclerosis'
    },
    'pneumoperitoneum': {
      keywords: ['pneumoperitoneum', 'free air', 'air under diaphragm', 'perforated'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/15094/cc00ef2b1cc452c017c18fe6821135_big_gallery.jpeg',
      altText: 'Example X-ray showing pneumoperitoneum',
      description: 'Free air appears as dark crescents under the diaphragm indicating perforation'
    },
    'hydronephrosis': {
      keywords: ['hydronephrosis', 'kidney swelling', 'dilated kidney', 'renal pelvis dilation'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/24875/adf9769a7bd13f6b9b89dc56dd86fb_big_gallery.jpeg',
      altText: 'Example ultrasound showing hydronephrosis',
      description: 'Hydronephrosis shows enlarged kidney with dilated collecting system'
    },
    'cirrhosis': {
      keywords: ['cirrhosis', 'liver disease', 'hepatic fibrosis', 'nodular liver'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/53923517/110064_big_gallery.jpeg',
      altText: 'Example CT showing cirrhosis',
      description: 'Cirrhosis shows nodular liver surface with altered texture and portal hypertension'
    },
    'pancreatitis': {
      keywords: ['pancreatitis', 'inflamed pancreas', 'pancreatic inflammation'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/595477/d63c92095afee076778b1fce6e79d6_big_gallery.jpeg',
      altText: 'Example CT showing pancreatitis',
      description: 'Pancreatitis shows enlarged, edematous pancreas with surrounding inflammation'
    },
    'bowel obstruction': {
      keywords: ['bowel obstruction', 'intestinal obstruction', 'blocked bowel', 'ileus'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/11381359/162fb46ddb2b9f97b0a8d5f1ee7272_big_gallery.jpg',
      altText: 'Example X-ray showing bowel obstruction',
      description: 'Bowel obstruction shows dilated loops of bowel with air-fluid levels'
    },
    'renal cell carcinoma': {
      keywords: ['renal cell carcinoma', 'kidney cancer', 'renal tumor', 'kidney mass'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/57718921/46._gallery.jpeg',
      altText: 'Example CT showing renal cell carcinoma',
      description: 'Renal cell carcinoma appears as enhancing mass arising from kidney'
    },
    'thyroid nodule': {
      keywords: ['thyroid nodule', 'thyroid mass', 'thyroid lesion'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/32476945/bdbdd89b0b0e501d7c17e8d9f1a3f5_big_gallery.jpeg',
      altText: 'Example ultrasound showing thyroid nodule',
      description: 'Thyroid nodules appear as discrete masses within thyroid gland'
    },
    'breast cancer': {
      keywords: ['breast cancer', 'breast mass', 'mammary carcinoma', 'breast lesion'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/d/d5/Mammo_breast_cancer.jpg',
      altText: 'Example mammogram showing breast cancer',
      description: 'Breast cancer shows as irregular spiculated mass with microcalcifications'
    },
    'atelectasis': {
      keywords: ['atelectasis', 'collapsed lung', 'lung collapse', 'partial collapse'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/583698/5383b773b0b3ca2ecdf35ee1f26e5a_big_gallery.jpg',
      altText: 'Example chest X-ray showing atelectasis',
      description: 'Atelectasis appears as increased density with volume loss'
    },
    'emphysema': {
      keywords: ['emphysema', 'copd', 'hyperinflation', 'bullae'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/382212/b9da26743a93f34c519f00aeb23578_gallery.jpg',
      altText: 'Example CT showing emphysema',
      description: 'Emphysema shows destruction of alveoli with hyperinflation and bullae'
    },
    'pulmonary fibrosis': {
      keywords: ['pulmonary fibrosis', 'interstitial lung disease', 'lung scarring', 'fibrosis'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/5353775/9bc8f92541d77c5b49145260f43763_gallery.jpg',
      altText: 'Example CT showing pulmonary fibrosis',
      description: 'Pulmonary fibrosis shows reticular pattern with honeycombing'
    },
    'sinusitis': {
      keywords: ['sinusitis', 'sinus infection', 'sinus inflammation'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/a/a8/Sinusitis_CT.jpg',
      altText: 'Example CT showing sinusitis',
      description: 'Sinusitis shows opacification of paranasal sinuses with air-fluid levels'
    },
    'orbital fracture': {
      keywords: ['orbital fracture', 'eye socket fracture', 'blowout fracture'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/54243544/coronal_soft.Seq302.Ser0.Img41_big_gallery.jpeg',
      altText: 'Example CT showing orbital fracture',
      description: 'Orbital fracture shows bone disruption with possible herniation of orbital contents'
    },
    'aortic dissection': {
      keywords: ['aortic dissection', 'dissection', 'aortic tear'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/587/6fd2c5081df13d6ae300b54a20e783_big_gallery.jpeg',
      altText: 'Example CT showing aortic dissection',
      description: 'Aortic dissection shows intimal flap separating true and false lumens'
    },
    'pericardial effusion': {
      keywords: ['pericardial effusion', 'fluid around heart', 'pericardial fluid'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/60518382/bf87561b6d5787b810f49d382dea62b387412d66c3fc608fc0c81b9ac8d8c132_big_gallery.jpeg',
      altText: 'Example echo showing pericardial effusion',
      description: 'Pericardial effusion shows dark fluid collection surrounding heart'
    },
    'splenic rupture': {
      keywords: ['splenic rupture', 'ruptured spleen', 'spleen injury'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/4/4f/Splenic_laceration.jpg',
      altText: 'Example CT showing splenic injury',
      description: 'Splenic rupture shows irregular contour with surrounding hemorrhage'
    },
    'ascites': {
      keywords: ['ascites', 'abdominal fluid', 'peritoneal fluid', 'fluid in abdomen'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/6954392/80b3fa11537b86a9df167e76d4c044_big_gallery.jpg',
      altText: 'Example CT showing ascites',
      description: 'Ascites appears as dark fluid collection in peritoneal cavity'
    },
    'acute respiratory distress': {
      keywords: ['ards', 'acute respiratory distress', 'white out'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/6/6a/ARDS.jpg',
      altText: 'Example chest X-ray showing ARDS',
      description: 'ARDS shows bilateral diffuse alveolar infiltrates'
    },
    'scoliosis': {
      keywords: ['scoliosis', 'spinal curvature', 'curved spine'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/17198/d6a5a89c7a0d95b2092dbd174516d6_big_gallery.jpeg',
      altText: 'Example X-ray showing scoliosis',
      description: 'Scoliosis shows lateral curvature of spine with vertebral rotation'
    },
    'osteomyelitis': {
      keywords: ['osteomyelitis', 'bone infection', 'infected bone'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/16522/8ada203fa69e9f76dfa3b06fc52f7fdd2222b0946e812010001c7c0541dd2d49_big_gallery.jpeg',
      altText: 'Example X-ray showing osteomyelitis',
      description: 'Osteomyelitis shows bone destruction with periosteal reaction'
    },
    'metastases': {
      keywords: ['metastases', 'metastatic', 'spread', 'mets'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/b/b4/Brain_metastases.jpg',
      altText: 'Example MRI showing metastases',
      description: 'Metastases appear as multiple enhancing lesions'
    },
    'abdominal aortic calcification': {
      keywords: ['calcification', 'calcified', 'vascular calcification'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/f/f8/Aortic_calcification.jpg',
      altText: 'Example X-ray showing vascular calcification',
      description: 'Calcification appears as bright white deposits along vessel walls'
    },
    'diverticulitis': {
      keywords: ['diverticulitis', 'diverticular disease', 'inflamed diverticulum'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/3582613/0df66543ffb697ca0c38555ca5ae01_gallery.jpg',
      altText: 'Example CT showing diverticulitis',
      description: 'Diverticulitis shows thickened bowel wall with inflamed diverticula'
    },
    'inguinal hernia': {
      keywords: ['hernia', 'inguinal hernia', 'ventral hernia', 'umbilical hernia'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/627161/f18e48456ba83cb291a10efffcccce_big_gallery.jpg',
      altText: 'Example CT showing inguinal hernia',
      description: 'Hernia shows bowel or fat protruding through abdominal wall defect'
    },
    'liver metastases': {
      keywords: ['liver metastases', 'hepatic metastases', 'liver mets'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/0/04/Liver_metastases.jpg',
      altText: 'Example CT showing liver metastases',
      description: 'Liver metastases appear as multiple low-density lesions'
    },
    'subdural hematoma': {
      keywords: ['subdural hematoma', 'subdural', 'sdh'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/2917407/76f8efa0129f2bbee07534be6dac09_gallery.jpg',
      altText: 'Example CT showing subdural hematoma',
      description: 'Subdural hematoma appears as crescentic blood collection'
    },
    'epidural hematoma': {
      keywords: ['epidural hematoma', 'epidural', 'edh'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/2917400/c1f043792d0a4b4e2511aa75f36113_gallery.jpg',
      altText: 'Example CT showing epidural hematoma',
      description: 'Epidural hematoma appears as biconvex lens-shaped blood collection'
    },
    'subarachnoid hemorrhage': {
      keywords: ['subarachnoid hemorrhage', 'subarachnoid', 'sah'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/30462007/f9b3048bebfeeb37c713a1db06a5ae_big_gallery.jpeg',
      altText: 'Example CT showing subarachnoid hemorrhage',
      description: 'Subarachnoid hemorrhage shows blood in sulci and cisterns'
    },
    'hydrocephalus': {
      keywords: ['hydrocephalus', 'enlarged ventricles', 'ventriculomegaly'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/8860052/2af75d166a92e01da2e2703ad565f3_big_gallery.jpeg',
      altText: 'Example CT showing hydrocephalus',
      description: 'Hydrocephalus shows abnormally enlarged cerebral ventricles'
    },
    'multiple sclerosis': {
      keywords: ['multiple sclerosis', 'ms', 'demyelination', 'white matter lesions'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/798/7a111ecd3bebcb930ce9f60ed18840_big_gallery.jpeg',
      altText: 'Example MRI showing multiple sclerosis',
      description: 'MS shows multiple white matter plaques on MRI'
    },
    'cervical spondylosis': {
      keywords: ['cervical spondylosis', 'neck arthritis', 'degenerative neck'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/b/b9/Cervical_spondylosis.jpg',
      altText: 'Example X-ray showing cervical spondylosis',
      description: 'Cervical spondylosis shows disc space narrowing with osteophytes'
    },
    'rotator cuff tear': {
      keywords: ['rotator cuff tear', 'shoulder tear', 'cuff tear'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/1181097/cf6188085df7990d397028a30ba5cd_big_gallery.jpg',
      altText: 'Example MRI showing rotator cuff tear',
      description: 'Rotator cuff tear shows discontinuity of tendon with fluid signal'
    },
    'meniscal tear': {
      keywords: ['meniscal tear', 'meniscus tear', 'knee tear'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/52121909/b7689ccd662e817b60eeef6b577677_big_gallery.jpeg',
      altText: 'Example MRI showing meniscal tear',
      description: 'Meniscal tear shows irregular signal within meniscus'
    },
    'acl tear': {
      keywords: ['acl tear', 'anterior cruciate ligament', 'ligament tear'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/590017/994f72bdb3c7c58a22fe52b41b8b5acfeac621ca2572799b785e91bcb688525e_big_gallery.jpeg',
      altText: 'Example MRI showing ACL tear',
      description: 'ACL tear shows discontinuity or absence of anterior cruciate ligament'
    },
    'achilles tendon rupture': {
      keywords: ['achilles rupture', 'achilles tear', 'tendon rupture'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/858/953975b108f02b51c197fa55814120_gallery.jpeg',
      altText: 'Example MRI showing Achilles rupture',
      description: 'Achilles rupture shows gap in tendon with surrounding fluid'
    },
    'hip fracture': {
      keywords: ['hip fracture', 'femoral neck fracture', 'intertrochanteric fracture'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/57897095/0._big_gallery.jpeg',
      altText: 'Example X-ray showing hip fracture',
      description: 'Hip fracture shows break in femoral neck or intertrochanteric region'
    },
    'scaphoid fracture': {
      keywords: ['scaphoid fracture', 'wrist fracture', 'navicular fracture'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/61880398/d3ce2589f8bb0a510c49a0a9c59c329bf235d16ed5203254169f45135ba36fb7_big_gallery.jpeg',
      altText: 'Example X-ray showing scaphoid fracture',
      description: 'Scaphoid fracture shows break through waist of scaphoid bone'
    },
    'vertebral compression fracture': {
      keywords: ['compression fracture', 'vertebral fracture', 'collapsed vertebra'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/c/cb/Compression_fracture.jpg',
      altText: 'Example X-ray showing compression fracture',
      description: 'Compression fracture shows loss of vertebral height with wedging'
    },
    'rib fracture': {
      keywords: ['rib fracture', 'broken rib', 'rib break'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/7866511/8742c6e7b8e74dbc77a2e307ae9255_big_gallery.jpg',
      altText: 'Example X-ray showing rib fracture',
      description: 'Rib fracture shows disruption of rib cortex with displacement'
    },
    'clavicle fracture': {
      keywords: ['clavicle fracture', 'broken collarbone', 'collar bone fracture'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/27227555/1704e1789edd0dfd3160b36baf9b796907d2f07c548bdd531bb9a42bd0f80a35_big_gallery.jpeg',
      altText: 'Example X-ray showing clavicle fracture',
      description: 'Clavicle fracture typically occurs at middle third with displacement'
    },
    'fatty liver': {
      keywords: ['fatty liver', 'hepatic steatosis', 'steatosis'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/29860/3668259b9776a8e4c04917f6d9170a_gallery.jpg',
      altText: 'Example ultrasound showing fatty liver',
      description: 'Fatty liver shows increased echogenicity with poor visualization of vessels'
    },
    'hepatomegaly': {
      keywords: ['hepatomegaly', 'enlarged liver', 'liver enlargement'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/25420/f4ad43586abb20167ec3ac23438ee0_big_gallery.jpeg',
      altText: 'Example CT showing hepatomegaly',
      description: 'Hepatomegaly shows liver extending below costal margin'
    },
    'splenomegaly': {
      keywords: ['splenomegaly', 'enlarged spleen', 'spleen enlargement'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/53415844/splenomegaly9201136_big_gallery.jpeg',
      altText: 'Example CT showing splenomegaly',
      description: 'Splenomegaly shows enlarged spleen extending beyond normal size'
    },
    'portal vein thrombosis': {
      keywords: ['portal vein thrombosis', 'portal vein clot', 'pvt'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/31196/f029a368a913d90cdefdaf67c2f108_big_gallery.jpg',
      altText: 'Example CT showing portal vein thrombosis',
      description: 'Portal vein thrombosis shows filling defect within portal vein'
    },
    'carotid stenosis': {
      keywords: ['carotid stenosis', 'carotid narrowing', 'carotid plaque'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/8807248/906b36856e433c3a2b3985b0bd00e2_big_gallery.jpg',
      altText: 'Example ultrasound showing carotid stenosis',
      description: 'Carotid stenosis shows narrowing of carotid artery with plaque'
    },
    'deep vein thrombosis': {
      keywords: ['deep vein thrombosis', 'dvt', 'leg clot', 'venous thrombosis'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/381423/33e6681df31b4d19e8cac6216155a1_big_gallery.jpg',
      altText: 'Example ultrasound showing DVT',
      description: 'DVT shows non-compressible vein with echogenic thrombus'
    },
    'ovarian cyst': {
      keywords: ['ovarian cyst', 'adnexal cyst', 'ovary cyst'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/0/07/Ovarian_cyst.jpg',
      altText: 'Example ultrasound showing ovarian cyst',
      description: 'Ovarian cyst appears as anechoic fluid-filled structure'
    },
    'uterine fibroids': {
      keywords: ['uterine fibroids', 'fibroid', 'leiomyoma', 'myoma'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/d/d2/Uterine_fibroid.jpg',
      altText: 'Example ultrasound showing uterine fibroid',
      description: 'Fibroids appear as well-defined hypoechoic masses in uterus'
    },
    'prostate enlargement': {
      keywords: ['prostate enlargement', 'bph', 'benign prostatic hyperplasia', 'enlarged prostate'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/420/dabb9954c6d02165278318fa035410_big_gallery.jpeg',
      altText: 'Example ultrasound showing enlarged prostate',
      description: 'BPH shows enlarged prostate gland compressing urethra'
    },
    'testicular torsion': {
      keywords: ['testicular torsion', 'twisted testicle', 'torsion'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/552240/0b56088cf1469bbb08f03ed87cc868_big_gallery.jpeg',
      altText: 'Example ultrasound showing testicular torsion',
      description: 'Testicular torsion shows absent or decreased blood flow to testicle'
    },
    'nephrolithiasis': {
      keywords: ['nephrolithiasis', 'urolithiasis', 'urinary stones'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/24804/1af425ddaf16fa001b5d129ec2ecbb_big_gallery.jpeg',
      altText: 'Example CT showing kidney stones',
      description: 'Kidney stones appear as high-density calcifications in collecting system'
    },
    'bladder stone': {
      keywords: ['bladder stone', 'vesical calculus', 'bladder calculi'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/55534935/Bladder_stones_big_gallery.jpeg',
      altText: 'Example X-ray showing bladder stone',
      description: 'Bladder stones appear as dense calcifications in bladder'
    },
    'urinary tract infection': {
      keywords: ['pyelonephritis', 'kidney infection', 'renal infection'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/480170/7e950becf5fae9067a38a5be46e065_big_gallery.jpg',
      altText: 'Example CT showing pyelonephritis',
      description: 'Pyelonephritis shows striated nephrogram with delayed enhancement'
    },
    'renal cyst': {
      keywords: ['renal cyst', 'kidney cyst', 'simple cyst'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/5816521/b3f4ff14786b8d73dea3df62d395ca_big_gallery.jpg',
      altText: 'Example CT showing renal cyst',
      description: 'Renal cysts appear as well-defined low-density fluid collections'
    },
    'polycystic kidney': {
      keywords: ['polycystic kidney', 'pkd', 'multiple kidney cysts'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/25248/d786b88a87abee8b2664bacd5807cd_big_gallery.jpeg',
      altText: 'Example CT showing polycystic kidney disease',
      description: 'Polycystic kidneys show bilateral enlarged kidneys with multiple cysts'
    },
    'adrenal adenoma': {
      keywords: ['adrenal adenoma', 'adrenal mass', 'adrenal nodule'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/53636477/s10_big_gallery.jpeg',
      altText: 'Example CT showing adrenal adenoma',
      description: 'Adrenal adenoma appears as well-circumscribed low-density mass'
    },
    'pheochromocytoma': {
      keywords: ['pheochromocytoma', 'adrenal tumor'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/b/b4/Pheochromocytoma.jpg',
      altText: 'Example CT showing pheochromocytoma',
      description: 'Pheochromocytoma shows intensely enhancing adrenal mass'
    },
    'thyroid goiter': {
      keywords: ['goiter', 'enlarged thyroid', 'thyroid enlargement'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/9149495/986d3656d7ca59a267fe0843dbbffd_gallery.jpeg',
      altText: 'Example ultrasound showing thyroid goiter',
      description: 'Goiter shows diffusely or nodularly enlarged thyroid gland'
    },
    'parathyroid adenoma': {
      keywords: ['parathyroid adenoma', 'parathyroid mass'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/1706437/b8ebcac7467e63627fe50c1aca4590_big_gallery.jpg',
      altText: 'Example ultrasound showing parathyroid adenoma',
      description: 'Parathyroid adenoma appears as hypoechoic mass behind thyroid'
    },
    'cushing syndrome': {
      keywords: ['cushing', 'pituitary adenoma', 'sellar mass'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/2838459/64fb6151f2ce05f6c5b70723df7599_big_gallery.jpg',
      altText: 'Example MRI showing pituitary adenoma',
      description: 'Pituitary adenoma shows enhancing sellar or suprasellar mass'
    },
    'acoustic neuroma': {
      keywords: ['acoustic neuroma', 'vestibular schwannoma', 'cerebellopontine angle mass'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/25854460/d5062bf8ea01f356463b88cb48b569_big_gallery.jpeg',
      altText: 'Example MRI showing acoustic neuroma',
      description: 'Acoustic neuroma shows enhancing mass in internal auditory canal'
    },
    'chiari malformation': {
      keywords: ['chiari malformation', 'cerebellar tonsillar herniation'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/59112961/1965cae05b02670fc62f9eec8ba4994d12d1ce0d50907b1256645ebc748cc3cb_gallery.jpeg',
      altText: 'Example MRI showing Chiari malformation',
      description: 'Chiari malformation shows cerebellar tonsils extending below foramen magnum'
    },
    'syringomyelia': {
      keywords: ['syringomyelia', 'syrinx', 'spinal cord cyst'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/1159985/7bc83e67867be3fa1cd5e28c5ee1f5_big_gallery.jpg',
      altText: 'Example MRI showing syringomyelia',
      description: 'Syringomyelia shows fluid-filled cavity within spinal cord'
    },
    'spondylolisthesis': {
      keywords: ['spondylolisthesis', 'vertebral slip', 'slipped vertebra'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/4092009/8ddb0422f1b694c63891f9deda56aa_big_gallery.jpg',
      altText: 'Example X-ray showing spondylolisthesis',
      description: 'Spondylolisthesis shows forward displacement of vertebra'
    },
    'ankylosing spondylitis': {
      keywords: ['ankylosing spondylitis', 'bamboo spine', 'fused spine'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/53731976/AS_gallery.jpeg',
      altText: 'Example X-ray showing ankylosing spondylitis',
      description: 'Ankylosing spondylitis shows vertebral fusion with syndesmophytes'
    },
    'esophageal cancer': {
      keywords: ['esophageal cancer', 'esophageal mass', 'esophageal tumor'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/1/12/Esophageal_cancer.jpg',
      altText: 'Example CT showing esophageal cancer',
      description: 'Esophageal cancer shows irregular esophageal wall thickening'
    },
    'gastric cancer': {
      keywords: ['gastric cancer', 'stomach cancer', 'gastric mass'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/9/94/Gastric_cancer.jpg',
      altText: 'Example CT showing gastric cancer',
      description: 'Gastric cancer shows irregular gastric wall thickening with mass'
    },
    'colon cancer': {
      keywords: ['colon cancer', 'colorectal cancer', 'bowel cancer'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/c/ca/Colon_cancer.jpg',
      altText: 'Example CT showing colon cancer',
      description: 'Colon cancer shows circumferential bowel wall thickening'
    },
    'crohn disease': {
      keywords: ['crohn', 'crohn disease', 'inflammatory bowel disease', 'ibd'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/7/7c/Crohn_disease.jpg',
      altText: 'Example CT showing Crohn disease',
      description: 'Crohn disease shows segmental bowel wall thickening with skip lesions'
    },
    'ulcerative colitis': {
      keywords: ['ulcerative colitis', 'uc', 'colitis'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/24800/eef03b2d007a2e191bcb3e514dfcfa_big_gallery.jpeg',
      altText: 'Example CT showing ulcerative colitis',
      description: 'Ulcerative colitis shows continuous colonic wall thickening'
    },
    'intussusception': {
      keywords: ['intussusception', 'telescoped bowel'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/55801502/Stool_big_gallery.jpeg',
      altText: 'Example CT showing intussusception',
      description: 'Intussusception shows target sign with bowel within bowel'
    },
    'volvulus': {
      keywords: ['volvulus', 'twisted bowel', 'sigmoid volvulus'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/22763/0312cc34edf2c38859b96c86aca03f_big_gallery.jpeg',
      altText: 'Example X-ray showing volvulus',
      description: 'Volvulus shows dilated twisted bowel loop with bird beak sign'
    },
    'mesenteric ischemia': {
      keywords: ['mesenteric ischemia', 'bowel ischemia', 'dead bowel'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/29886933/30cd3c2439375d1f5c3e753f4faea7bfa7659803a33f477f48736f70ab58cac7_big_gallery.jpeg',
      altText: 'Example CT showing mesenteric ischemia',
      description: 'Mesenteric ischemia shows bowel wall thickening with pneumatosis'
    },
    'pneumatosis intestinalis': {
      keywords: ['pneumatosis', 'air in bowel wall', 'intramural air'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/545624/0459ff57d70fb62f5317efc59e84c7_big_gallery.jpg',
      altText: 'Example CT showing pneumatosis intestinalis',
      description: 'Pneumatosis shows air within bowel wall appearing as linear lucencies'
    },
    'cholecystitis': {
      keywords: ['cholecystitis', 'gallbladder inflammation', 'inflamed gallbladder'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/563856/a61a99793f19cdb0f19d515a8466fd_big_gallery.jpg',
      altText: 'Example ultrasound showing cholecystitis',
      description: 'Cholecystitis shows thickened gallbladder wall with pericholecystic fluid'
    },
    'pancreatic cancer': {
      keywords: ['pancreatic cancer', 'pancreatic mass', 'pancreatic tumor'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/54008125/110173_big_gallery.jpeg',
      altText: 'Example CT showing pancreatic cancer',
      description: 'Pancreatic cancer shows hypoenhancing mass with vascular involvement'
    },
    'choledocholithiasis': {
      keywords: ['choledocholithiasis', 'bile duct stone', 'cbd stone'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/597090/fb776fad141c861541f0702defcdde_big_gallery.jpg',
      altText: 'Example MRCP showing bile duct stone',
      description: 'Bile duct stone shows filling defect in common bile duct with dilation'
    },
    'biliary obstruction': {
      keywords: ['biliary obstruction', 'bile duct obstruction', 'biliary dilation'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/a/a7/Biliary_obstruction.jpg',
      altText: 'Example CT showing biliary obstruction',
      description: 'Biliary obstruction shows dilated bile ducts proximal to obstruction'
    },
    'hepatocellular carcinoma': {
      keywords: ['hepatocellular carcinoma', 'hcc', 'liver cancer'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/29041/a2f908f1245a8c86819f56633bc772_big_gallery.jpg',
      altText: 'Example CT showing hepatocellular carcinoma',
      description: 'HCC shows arterial enhancement with washout in portal venous phase'
    },
    'portal hypertension': {
      keywords: ['portal hypertension', 'varices', 'esophageal varices'],
      imageUrl: 'https://prod-images-static.radiopaedia.org/images/29588/729aca4f2417d8cfb9e13f9d6cd50b_big_gallery.jpg',
      altText: 'Example CT showing portal hypertension',
      description: 'Portal hypertension shows enlarged portal vein with collateral vessels'
    },
    'budd-chiari syndrome': {
      keywords: ['budd-chiari', 'hepatic vein thrombosis'],
      imageUrl: 'https://upload.wikimedia.org/wikipedia/commons/c/c8/Budd_chiari.jpg',
      altText: 'Example CT showing Budd-Chiari syndrome',
      description: 'Budd-Chiari shows hepatic vein thrombosis with congested liver'
    }
  };

  /**
   * Detect medical conditions mentioned in text
   */
  function detectConditions(text) {
    const normalizedText = (text || '').toLowerCase();
    const detectedConditions = [];
    
    for (const [condition, data] of Object.entries(CONDITION_EXAMPLES)) {
      for (const keyword of data.keywords) {
        if (normalizedText.includes(keyword)) {
          if (!detectedConditions.find(c => c.name === condition)) {
            detectedConditions.push({
              name: condition,
              ...data
            });
          }
          break;
        }
      }
    }
    
    return detectedConditions;
  }


  // Region-specific keywords for more precise highlighting
  const REGION_KEYWORDS = {
    'brain': {
      'frontal': ['frontal', 'prefrontal', 'anterior'],
      'parietal': ['parietal', 'posterior'],
      'temporal': ['temporal', 'lateral'],
      'occipital': ['occipital', 'back'],
      'cerebellum': ['cerebellum', 'cerebellar'],
      'brainstem': ['brainstem', 'medulla', 'pons']
    },
    'heart': {
      'left-ventricle': ['left ventricle', 'lv', 'apical', 'apex'],
      'right-ventricle': ['right ventricle', 'rv'],
      'left-atrium': ['left atrium', 'la'],
      'right-atrium': ['right atrium', 'ra'],
      'valves': ['valve', 'aortic', 'mitral', 'tricuspid', 'pulmonary valve']
    },
    'lungs': {
      'upper-right': ['right upper lobe', 'rul', 'right apex'],
      'middle-right': ['right middle lobe', 'rml'],
      'lower-right': ['right lower lobe', 'rll', 'right base'],
      'upper-left': ['left upper lobe', 'lul', 'left apex'],
      'lower-left': ['left lower lobe', 'lll', 'left base']
    },
    'liver': {
      'right-lobe': ['right lobe', 'right hepatic'],
      'left-lobe': ['left lobe', 'left hepatic'],
      'caudate': ['caudate'],
      'porta': ['porta hepatis', 'portal']
    },
    'kidney': {
      'upper-pole': ['upper pole', 'superior pole'],
      'lower-pole': ['lower pole', 'inferior pole'],
      'cortex': ['cortex', 'cortical'],
      'medulla': ['medulla', 'medullary']
    }
  };

  /**
   * Detect specific regions mentioned in text for an organ
   */
  function detectRegions(text, organ) {
    const normalizedText = (text || '').toLowerCase();
    const detectedRegions = [];
    
    if (REGION_KEYWORDS[organ]) {
      for (const [region, keywords] of Object.entries(REGION_KEYWORDS[organ])) {
        for (const keyword of keywords) {
          if (normalizedText.includes(keyword)) {
            if (!detectedRegions.includes(region)) {
              detectedRegions.push(region);
            }
            break;
          }
        }
      }
    }
    
    return detectedRegions;
  }

  /**
   * Extract context around organ mentions to show what's wrong
   */
  function extractOrganContext(text, organ) {
    const normalizedText = (text || '').toLowerCase();
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
    const relevantSentences = [];
    
    // Find sentences mentioning this organ
    for (const sentence of sentences) {
      const lowerSentence = sentence.toLowerCase();
      const keywords = ORGAN_KEYWORDS[organ] || [];
      
      for (const keyword of keywords) {
        if (lowerSentence.includes(keyword)) {
          relevantSentences.push(sentence.trim());
          break;
        }
      }
    }
    
    return relevantSentences.slice(0, 2); // Return up to 2 most relevant sentences
  }


  /**
   * Detect organs mentioned in text
   */
  function detectOrgans(text) {
    const normalizedText = (text || '').toLowerCase();
    const detected = [];
    
    for (const [organ, keywords] of Object.entries(ORGAN_KEYWORDS)) {
      for (const keyword of keywords) {
        if (normalizedText.includes(keyword)) {
          if (!detected.includes(organ)) {
            detected.push(organ);
          }
          break;
        }
      }
    }
    
    return detected;
  }

  /**
   * Check if organ findings indicate normalcy (no issues)
   */
  function isOrganNormal(text, organ) {
    const normalizedText = (text || '').toLowerCase();
    const keywords = ORGAN_KEYWORDS[organ] || [];
    
    // Find sentences mentioning this organ
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
    const organSentences = [];
    
    for (const sentence of sentences) {
      const lowerSentence = sentence.toLowerCase();
      for (const keyword of keywords) {
        if (lowerSentence.includes(keyword)) {
          organSentences.push(sentence.toLowerCase());
          break;
        }
      }
    }
    
    // Check for normal indicators
    const normalIndicators = [
      'normal',
      'unremarkable',
      'no abnormality',
      'no evidence',
      'within normal limits',
      'looks normal',
      'appear normal',
      'appears normal',
      'no pathology',
      'no acute',
      'clear'
    ];
    
    const abnormalIndicators = [
      'abnormal',
      'lump',
      'mass',
      'lesion',
      'tumor',
      'enlarged',
      'widened',
      'blockage',
      'fracture',
      'bleeding',
      'swelling',
      'edema',
      'inflammation',
      'infection',
      'cyst',
      'stone',
      'nodule',
      'opacity',
      'consolidation',
      'effusion',
      'concern'
    ];
    
    let normalCount = 0;
    let abnormalCount = 0;
    
    for (const sentence of organSentences) {
      for (const indicator of normalIndicators) {
        if (sentence.includes(indicator)) {
          normalCount++;
          break;
        }
      }
      for (const indicator of abnormalIndicators) {
        if (sentence.includes(indicator)) {
          abnormalCount++;
          break;
        }
      }
    }
    
    // Return true if normal indicators found and no abnormal indicators
    return normalCount > 0 && abnormalCount === 0;
  }

  /**
   * Create organ visualization section
   */
  function createOrganSection(organ, isAvailable, reportText) {
    const section = document.createElement('section');
    section.className = 'organ-anatomy-section';
    section.style.cssText = 'margin: 1rem; padding: 1rem; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; flex: 1; min-width: 280px; max-width: 450px;';
    
    const title = document.createElement('h3');
    title.textContent = organ.charAt(0).toUpperCase() + organ.slice(1) + ' Anatomy';
    title.style.cssText = 'margin: 0 0 0.75rem 0; color: var(--text); font-size: 1.1rem;';
    section.appendChild(title);

    // Extract specific regions and context
    const detectedRegions = detectRegions(reportText, organ);
    const context = extractOrganContext(reportText, organ);
    
    // Show what was found in the report
    if (context.length > 0) {
      const contextBox = document.createElement('div');
      contextBox.style.cssText = 'margin-bottom: 0.75rem; padding: 0.75rem; background: rgba(239, 68, 68, 0.08); border-left: 4px solid #ef4444; border-radius: 6px;';
      contextBox.innerHTML = `
        <p style="margin: 0 0 0.4rem 0; font-weight: 600; color: var(--text); font-size: 0.85rem;">📋 Report findings:</p>
        <p style="margin: 0; color: var(--text); font-size: 0.85rem; line-height: 1.5;">${context.join(' ')}</p>
      `;
      section.appendChild(contextBox);
    }
    
    // Show detected regions
    if (detectedRegions.length > 0) {
      const regionInfo = document.createElement('div');
      regionInfo.style.cssText = 'margin-bottom: 0.75rem; padding: 0.6rem 0.75rem; background: rgba(16, 185, 129, 0.08); border-left: 4px solid var(--mint); border-radius: 6px;';
      const regionList = detectedRegions.map(r => `<strong>${r.replace(/-/g, ' ')}</strong>`).join(', ');
      regionInfo.innerHTML = `
        <p style="margin: 0; color: var(--text); font-size: 0.85rem;">
          🎯 Specific region(s): ${regionList}
        </p>
      `;
      section.appendChild(regionInfo);
    }

    if (isAvailable) {
      // Special handling for kidneys - show both left and right
      if (organ === 'kidney' || organ === 'kidneys') {
        const kidneyWrapper = document.createElement('div');
        kidneyWrapper.style.cssText = 'display: flex; gap: 1rem; justify-content: center; align-items: center; flex-wrap: wrap;';
        
        // Left kidney
        const leftKidneyDiv = document.createElement('div');
        leftKidneyDiv.style.cssText = 'position: relative; width: 45%; min-width: 120px;';
        const leftImg = document.createElement('img');
        leftImg.src = AVAILABLE_ORGANS[organ];
        leftImg.alt = 'Left kidney anatomy';
        leftImg.style.cssText = 'width: 100%; height: auto; display: block; transform: scaleX(-1);'; // Mirror
        leftKidneyDiv.appendChild(leftImg);
        
        const leftLabel = document.createElement('div');
        leftLabel.textContent = 'Left Kidney';
        leftLabel.style.cssText = 'text-align: center; margin-top: 0.5rem; font-size: 0.8rem; color: var(--muted); font-weight: 600;';
        leftKidneyDiv.appendChild(leftLabel);
        
        // Right kidney
        const rightKidneyDiv = document.createElement('div');
        rightKidneyDiv.style.cssText = 'position: relative; width: 45%; min-width: 120px;';
        const rightImg = document.createElement('img');
        rightImg.src = AVAILABLE_ORGANS[organ];
        rightImg.alt = 'Right kidney anatomy';
        rightImg.style.cssText = 'width: 100%; height: auto; display: block;';
        rightKidneyDiv.appendChild(rightImg);
        
        const rightLabel = document.createElement('div');
        rightLabel.textContent = 'Right Kidney';
        rightLabel.style.cssText = 'text-align: center; margin-top: 0.5rem; font-size: 0.8rem; color: var(--muted); font-weight: 600;';
        rightKidneyDiv.appendChild(rightLabel);
        
        // Add overlays if there are findings
        if (detectedRegions.length > 0 || context.length > 0) {
          const leftOverlay = document.createElement('div');
          leftOverlay.style.cssText = `
            position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(239, 68, 68, 0.15); border: 2px solid #ef4444;
            border-radius: 8px; pointer-events: none;
            animation: pulseHighlight 2s ease-in-out infinite;
          `;
          leftKidneyDiv.insertBefore(leftOverlay, leftLabel);
          
          const rightOverlay = document.createElement('div');
          rightOverlay.style.cssText = `
            position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(239, 68, 68, 0.15); border: 2px solid #ef4444;
            border-radius: 8px; pointer-events: none;
            animation: pulseHighlight 2s ease-in-out infinite;
          `;
          rightKidneyDiv.insertBefore(rightOverlay, rightLabel);
        }
        
        kidneyWrapper.appendChild(leftKidneyDiv);
        kidneyWrapper.appendChild(rightKidneyDiv);
        section.appendChild(kidneyWrapper);
        
        if (detectedRegions.length > 0 || context.length > 0) {
          const legend = document.createElement('div');
          legend.style.cssText = 'margin-top: 0.75rem; text-align: center; color: var(--muted); font-size: 0.8rem;';
          legend.innerHTML = `
            <span style="display: inline-block; width: 12px; height: 12px; background: #ef4444; border-radius: 3px; vertical-align: middle; margin-right: 6px; opacity: 0.7;"></span> 
            ${detectedRegions.length > 0 ? 'Affected region(s) highlighted' : 'Area mentioned in report'}
          `;
          section.appendChild(legend);
        }
      } else {
        // Regular single organ display
        const imageWrapper = document.createElement('div');
        imageWrapper.style.cssText = 'position: relative; max-width: 100%; margin: 0 auto;';
        
        const img = document.createElement('img');
        img.src = AVAILABLE_ORGANS[organ];
        img.alt = organ + ' anatomy diagram';
        img.style.cssText = 'width: 100%; height: auto; display: block;';
        
        // Red overlay for highlighting - only if specific regions detected
        if (detectedRegions.length > 0 || context.length > 0) {
          const overlay = document.createElement('div');
          overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(239, 68, 68, 0.15);
            border: 3px solid #ef4444;
            border-radius: 8px;
            pointer-events: none;
            animation: pulseHighlight 2s ease-in-out infinite;
          `;
          
          imageWrapper.appendChild(img);
          imageWrapper.appendChild(overlay);
          
          const legend = document.createElement('div');
          legend.style.cssText = 'margin-top: 0.75rem; text-align: center; color: var(--muted); font-size: 0.8rem;';
          legend.innerHTML = `
            <span style="display: inline-block; width: 12px; height: 12px; background: #ef4444; border-radius: 3px; vertical-align: middle; margin-right: 6px; opacity: 0.7;"></span> 
            ${detectedRegions.length > 0 ? 'Affected region(s) highlighted' : 'Area mentioned in report'}
          `;
          section.appendChild(imageWrapper);
          section.appendChild(legend);
        } else {
          // No specific findings - don't show anything
          return null;
        }
      }
    } else {
      const unavailable = document.createElement('div');
      unavailable.style.cssText = 'padding: 1.5rem; text-align: center; background: rgba(239, 68, 68, 0.1); border: 2px dashed var(--border); border-radius: 8px;';
      unavailable.innerHTML = `
        <p style="margin: 0; color: var(--muted); font-size: 0.9rem;">
          📋 Anatomy diagram for <strong style="color: var(--text);">${organ}</strong> is not available yet.
        </p>
        <p style="margin: 0.5rem 0 0 0; color: var(--muted); font-size: 0.8rem;">
          We are working on adding more organ visualizations.
        </p>
      `;
      section.appendChild(unavailable);
    }
    
    return section;
  }

  /**
   * Create a section displaying an example medical image for a detected condition
   * @param {string} conditionName - The name of the medical condition
   * @param {Object} conditionData - Object with imageUrl, altText, description
   * @returns {HTMLElement|null} The condition example section or null
   */
  function createConditionExampleSection(conditionName, conditionData) {
    const section = document.createElement('div');
    section.className = 'condition-example-section';
    section.style.cssText = 'flex: 1 1 100%; min-width: 280px; max-width: 100%; padding: 1.5rem; background: var(--panel); border: 3px solid #ff9800; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);';
    
    // Title
    const title = document.createElement('h3');
    title.style.cssText = 'margin: 0 0 1rem 0; font-size: 1.1rem; color: var(--text); display: flex; align-items: center; gap: 0.5rem;';
    title.innerHTML = `<span style="font-size: 1.3rem;">📊</span> Example: ${conditionName.charAt(0).toUpperCase() + conditionName.slice(1)}`;
    section.appendChild(title);
    
    // Prominent disclaimer box at the top
    const disclaimerTop = document.createElement('div');
    disclaimerTop.className = 'disclaimer-box';
    disclaimerTop.style.cssText = 'background: rgba(255, 165, 0, 0.2); border-left: 5px solid #ff9800; padding: 1rem; margin-bottom: 1rem; border-radius: 6px;';
    disclaimerTop.innerHTML = `
      <p style="margin: 0; color: #ff9800; font-weight: bold; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;">
        <span style="font-size: 1.5rem;">⚠️</span> EXAMPLE IMAGE ONLY - NOT YOUR ACTUAL SCAN
      </p>
      <p style="margin: 0.5rem 0 0 0; color: var(--text); font-size: 0.85rem;">
        This is a reference image from medical literature. Your scan may look completely different. 
        <strong>Do NOT use this to self-diagnose.</strong> This is just an educational assumption.
      </p>
    `;
    section.appendChild(disclaimerTop);
    
    // Image container with loading/error handling
    const imageContainer = document.createElement('div');
    imageContainer.style.cssText = 'margin: 1rem 0; text-align: center; background: rgba(0,0,0,0.05); border-radius: 8px; padding: 1rem;';
    
    const img = document.createElement('img');
    img.src = conditionData.imageUrl;
    img.alt = conditionData.altText;
    img.style.cssText = 'max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);';
    img.loading = 'lazy';
    
    // Handle image load errors
    img.onerror = function() {
      imageContainer.innerHTML = `
        <p style="color: var(--muted); font-size: 0.9rem; margin: 1rem 0;">
          ⚠️ Example image could not be loaded. Please consult your doctor for information about this condition.
        </p>
      `;
    };
    
    imageContainer.appendChild(img);
    section.appendChild(imageContainer);
    
    // Description
    if (conditionData.description) {
      const description = document.createElement('p');
      description.style.cssText = 'margin: 1rem 0; color: var(--muted); font-size: 0.9rem; line-height: 1.5;';
      description.textContent = conditionData.description;
      section.appendChild(description);
    }
    
    // Bottom disclaimer
    const disclaimerBottom = document.createElement('div');
    disclaimerBottom.style.cssText = 'margin-top: 1rem; padding: 0.75rem; background: rgba(239, 68, 68, 0.1); border-radius: 6px;';
    disclaimerBottom.innerHTML = `
      <p style="margin: 0; color: var(--muted); font-size: 0.8rem; text-align: center;">
        <strong>Important:</strong> Your radiologist will provide accurate interpretation. 
        This is just a reference image and may not represent your specific case.
      </p>
    `;
    section.appendChild(disclaimerBottom);
    
    return section;
  }

  /**
   * Initialize organ highlighting
   */
  function initOrganHighlighting() {
    // Get report text from structured data
    const findingsElement = document.querySelector('[data-findings-text]');
    const conclusionElement = document.querySelector('[data-conclusion-text]');
    const studyElement = document.querySelector('[data-study-type]');
    
    let reportText = '';
    if (findingsElement) reportText += findingsElement.dataset.findingsText || '';
    if (conclusionElement) reportText += ' ' + (conclusionElement.dataset.conclusionText || '');
    if (studyElement) reportText += ' ' + (studyElement.dataset.studyType || '');
    
    // Fallback: try to get from visible text
    if (!reportText.trim()) {
      const simpleOutput = document.querySelector('.simple-output');
      if (simpleOutput) {
        reportText = simpleOutput.textContent || '';
      }
    }
    
    if (!reportText.trim()) {
      console.log('Organ highlighting: No report text found');
      return;
    }
    
    // Detect organs
    const detectedOrgans = detectOrgans(reportText);
    console.log('Detected organs:', detectedOrgans);
    
    if (detectedOrgans.length === 0) {
      console.log('Organ highlighting: No organs detected');
      return;
    }
    
    // Find or create container for organ sections
    let container = document.getElementById('organ-anatomy-container');
    if (!container) {
      // Insert after body diagram section
      const bodyDiagram = document.getElementById('diagram-container');
      if (bodyDiagram && bodyDiagram.parentElement) {
        container = document.createElement('div');
        container.id = 'organ-anatomy-container';
        bodyDiagram.parentElement.insertAdjacentElement('afterend', container);
      } else {
        // Fallback: insert in main content
        const mainContent = document.querySelector('main.content');
        if (mainContent) {
          container = document.createElement('div');
          container.id = 'organ-anatomy-container';
          mainContent.appendChild(container);
        }
      }
    }
    
    if (!container) {
      console.error('Organ highlighting: Could not find or create container');
      return;
    }
    
    // Add CSS styles for grid layout and animations
    if (!document.getElementById('organ-highlight-styles')) {
      const style = document.createElement('style');
      style.id = 'organ-highlight-styles';
      style.textContent = `
        @keyframes pulseHighlight {
          0%, 100% { opacity: 0.25; }
          50% { opacity: 0.4; }
        }
        #organ-anatomy-container {
          display: flex;
          flex-wrap: wrap;
          gap: 1rem;
          margin: 2rem 0;
        }
        .light .organ-anatomy-section {
          background: var(--panel) !important;
        }
        .light .organ-anatomy-section h3 {
          color: var(--text) !important;
        }
        @media (max-width: 768px) {
          #organ-anatomy-container {
            flex-direction: column;
          }
          .organ-anatomy-section {
            max-width: 100% !important;
          }
        }
      `;
      document.head.appendChild(style);
    }
    
    // Create sections for each detected organ, filtering out normal ones
    let sectionsAdded = 0;
    detectedOrgans.forEach(organ => {
      // Skip organs that appear normal
      if (isOrganNormal(reportText, organ)) {
        console.log('Skipping ' + organ + ' - appears normal');
        return;
      }
      
      const isAvailable = AVAILABLE_ORGANS.hasOwnProperty(organ);
      const section = createOrganSection(organ, isAvailable, reportText);
      
      // Only add if section was created (not null)
      if (section) {
        container.appendChild(section);
        sectionsAdded++;
      }
    });
    
    console.log('Organ highlighting complete: ' + sectionsAdded + ' organs visualized (out of ' + detectedOrgans.length + ' detected)');
    
    // Detect and display example images for medical conditions
    const detectedConditions = detectConditions(reportText);
    console.log('Detected conditions:', detectedConditions);
    
    if (detectedConditions.length > 0) {
      // Add a separator/header before condition examples
      const conditionHeader = document.createElement('div');
      conditionHeader.style.cssText = 'flex: 1 1 100%; margin-top: 1.5rem; padding: 1rem; background: rgba(255, 165, 0, 0.1); border-radius: 8px;';
      conditionHeader.innerHTML = `
        <h3 style="margin: 0; color: var(--text); font-size: 1.2rem; display: flex; align-items: center; gap: 0.5rem;">
          <span style="font-size: 1.4rem;">📚</span> Educational Reference Images
        </h3>
        <p style="margin: 0.5rem 0 0 0; color: var(--muted); font-size: 0.85rem;">
          Based on keywords in your report, here are some example medical images for educational purposes only.
        </p>
      `;
      container.appendChild(conditionHeader);
      
      // Create section for each detected condition
      detectedConditions.forEach(condition => {
        const conditionSection = createConditionExampleSection(condition.name, condition);
        if (conditionSection) {
          container.appendChild(conditionSection);
        }
      });
      
      console.log('Condition examples displayed: ' + detectedConditions.length);
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOrganHighlighting);
  } else {
    initOrganHighlighting();
  }

})();
