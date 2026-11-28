import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { IconCheck, IconShield } from '../components/LineIcons.jsx';

const COPY = {
  en: {
    langLabel: 'English',
    badge: 'DPDP Act 2023 Compliant • Plain-Language Privacy Notice',
    title: 'Your Privacy Promise on HunarLink',
    subtitle:
      'Built for Jammu & Kashmir’s artisans and collectors worldwide. We collect only what is necessary to craft, verify GI provenance, and deliver your heirloom safely.',
    cards: [
      {
        heading: '1. Data We Collect & Why (Purpose Limitation)',
        items: [
          'Buyers: Name, email, delivery addresses, and order history to process orders and issue GI Ownership Passports.',
          'Artisans: Workshop name, craft specialty, district cluster, and verification document (stripped of EXIF/GPS photo metadata before storage).',
          'Reviews: You can hide your name & city anytime with “Post anonymously as Anonymous Collector”.'
        ]
      },
      {
        heading: '2. Zero Raw Card Data & No Escrow Holding',
        items: [
          'HunarLink never sees, handles, or stores your card number or CVV (PCI-DSS SAQ-A via Razorpay Hosted Checkout) or Cash-on-Delivery confirmation.',
          'Admin portals never expose database password hashes or unwatermarked KYC identity previews.'
        ]
      },
      {
        heading: '3. Age Policy (18+ Confirmation)',
        items: [
          'In line with Section 9 of India’s Digital Personal Data Protection (DPDP) Act 2023, HunarLink accounts and artisan onboarding require users to be 18 years of age or older.'
        ]
      },
      {
        heading: '4. Your DPDP Rights (Access, Correction, Export, Erasure)',
        items: [
          'Export a full machine-readable JSON copy of your profile, addresses, orders, reviews, and consent history from My Profile.',
          'Withdraw optional marketing or analytics consent with one click without affecting orders.',
          'Permanently delete your account and purge saved addresses and consent records from My Profile.'
        ]
      }
    ],
    grievanceTitle: 'Grievance & Data Protection Officer',
    grievanceBody:
      'Questions or data-erasure requests? Email our DPDP Grievance Desk at privacy@hunarlink.in (response target: 72 hours, maximum statutory window: 30 days).',
    ctaProfile: 'Manage Privacy & Export Data',
    ctaHome: 'Return to Marketplace'
  },
  hi: {
    langLabel: 'हिन्दी (Hindi)',
    badge: 'DPDP अधिनियम 2023 अनुपालन • सरल गोपनीयता सूचना',
    title: 'HunarLink पर आपकी गोपनीयता का वादा',
    subtitle:
      'जम्मू और कश्मीर के कारीगरों और खरीदारों के लिए निर्मित। हम केवल वही जानकारी लेते हैं जो ऑर्डर डिलीवरी और GI प्रमाणपत्र के लिए आवश्यक है।',
    cards: [
      {
        heading: '1. हम कौन-सा डेटा लेते हैं और क्यों',
        items: [
          'खरीदार: नाम, ईमेल, डिलीवरी पता और ऑर्डर इतिहास (केवल ऑर्डर और GI पासपोर्ट जारी करने हेतु)।',
          'कारीगर: कार्यशाला का नाम, शिल्प श्रेणी, जिला और सत्यापन दस्तावेज़ (स्टोर करने से पहले फोटो से GPS/EXIF मेटाडेटा हटाया जाता है)।',
          'समीक्षाएँ: आप अपना नाम व शहर छुपाकर “Anonymous Collector” के रूप में समीक्षा लिख सकते हैं।'
        ]
      },
      {
        heading: '2. कार्ड नंबर/CVV संग्रहण नहीं',
        items: [
          'HunarLink कभी भी आपका कार्ड नंबर या CVV संग्रहीत नहीं करता। ऑनलाइन भुगतान सीधे Razorpay होस्टेड चेकआउट द्वारा सुरक्षित रूप से प्रोसेस होता है।',
          'एडमिन पैनल में कोई पासवर्ड हैश प्रदर्शित नहीं किया जाता।'
        ]
      },
      {
        heading: '3. आयु नीति (18+)',
        items: [
          'DPDP अधिनियम 2023 की धारा 9 के अनुसार, खाता बनाने और कारीगर पंजीकरण के लिए उपयोगकर्ता की आयु 18 वर्ष या अधिक होना आवश्यक है।'
        ]
      },
      {
        heading: '4. आपके अधिकार (डेटा एक्सपोर्ट व खाता विलोपन)',
        items: [
          'My Profile में जाकर आप अपने पूरे डेटा की JSON कॉपी डाउनलोड कर सकते हैं।',
          'आप किसी भी समय मार्केटिंग या एनालिटिक्स सहमति वापस ले सकते हैं या अपना खाता स्थायी रूप से हटा सकते हैं।'
        ]
      }
    ],
    grievanceTitle: 'शिकायत एवं डेटा संरक्षण अधिकारी',
    grievanceBody:
      'डेटा से जुड़े किसी भी प्रश्न या शिकायत के लिए privacy@hunarlink.in पर संपर्क करें (लक्षित उत्तर समय: 72 घंटे)।',
    ctaProfile: 'डेटा एक्सपोर्ट व सेटिंग्स खोलें',
    ctaHome: 'मार्केटप्लेस पर लौटें'
  },
  ks: {
    langLabel: 'کٲشُر / Kashmiri',
    badge: 'DPDP ایکٹ 2023 • سادہ رازداری نوٹس (Kashmiri)',
    title: 'HunarLink پیٹھ تُہنز رازداری ہُند وعدہ',
    subtitle:
      'جموں تہٕ کشمیر کؠن کارؠگرن تہٕ خریٖدارن باپتھ۔ اسہِ چھےٚ صرف سۄ معلومات رٹان یۄس تُہند آرڈر واتناونہٕ تہٕ GI سندِ باپتھ ضروری چھےٚ۔',
    cards: [
      {
        heading: '1. ضروری معلومات تہٕ حفاظت',
        items: [
          'خریٖدار: ناو، ای میل تہٕ پتہ صرف ڈلیوری تہٕ GI پاسپورٹ باپتھ۔',
          'کارؠگر: کارخانہٕ تہٕ دستاویز (تصویر منٛز GPS/EXIF معلومات چھُ محفوظ کرنہٕ برٛونٛہہ صاف کرنہٕ یوان)۔',
          'ریویو: تُہؠ ہؠکِو پنُن ناو تہٕ شہر لُکٲوِتھ ریویو لؠکھتھ۔'
        ]
      },
      {
        heading: '2. بینک کارڈ تہٕ ادائیگی ہٕنٛز حفاظت',
        items: [
          'HunarLink چھُ نہٕ زانٛہہ تہِ کارڈ نمبر یا CVV جمع کران۔ آن لائن ادائیگی چھےٚ Razorpay محفوظ چیک آؤٹ ذٔریعہٕ گژھان۔'
        ]
      },
      {
        heading: '3. 18+ عمر ہٕنٛز شرط',
        items: [
          'قانون مطٲبق، HunarLink اکاؤنٹ بناونہٕ باپتھ گژھِ صارف کم از کم 18 وُہُر آسن۔'
        ]
      },
      {
        heading: '4. تُہند حق (JSON ڈاؤنلوڈ تہٕ اکاؤنٹ مؠٹاون)',
        items: [
          'My Profile منٛز گٔژھتھ ہؠکِو تُہؠ پنُن سٲری ڈیٹا ڈاؤنلوڈ کٔرتھ یا اکاؤنٹ ہمیشہٕ باپتھ ختم کٔرتھ۔'
        ]
      }
    ],
    grievanceTitle: 'رازداری مدد تہٕ شکایت',
    grievanceBody:
      'مدد باپتھ لؠکھِو privacy@hunarlink.in پیٹھ (72 گھنٹن اندر جواب)۔',
    ctaProfile: 'پروفائل تہٕ ڈیٹا کنٹرول',
    ctaHome: 'واپس دکانس پیٹھ'
  }
};

export default function PrivacyPromisePage() {
  const [lang, setLang] = useState('en');
  const content = COPY[lang] || COPY.en;
  const isRtl = lang === 'ks';

  return (
    <main
      id="main-content"
      dir={isRtl ? 'rtl' : 'ltr'}
      style={{
        maxWidth: '920px',
        margin: '0 auto',
        padding: '36px 20px 72px'
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap',
          marginBottom: '20px'
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 14px',
            borderRadius: '999px',
            background: '#edf5ef',
            border: '1px solid rgba(11, 58, 38, 0.2)',
            color: '#0B3A26',
            fontSize: '0.78rem',
            fontWeight: 700
          }}
        >
          <IconShield size={14} />
          {content.badge}
        </span>

        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }} role="group" aria-label="Notice Language">
          {Object.entries(COPY).map(([code, entry]) => (
            <button
              key={code}
              type="button"
              onClick={() => setLang(code)}
              style={{
                padding: '6px 12px',
                borderRadius: '999px',
                border: lang === code ? '1px solid #0B3A26' : '1px solid rgba(20,56,42,0.2)',
                background: lang === code ? '#0B3A26' : '#fff',
                color: lang === code ? '#fff' : '#14382a',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              {entry.langLabel}
            </button>
          ))}
        </div>
      </div>

      <h1
        style={{
          fontFamily: 'var(--font-serif)',
          fontSize: 'clamp(1.85rem, 3.2vw, 2.45rem)',
          color: '#10281e',
          marginBottom: '10px'
        }}
      >
        {content.title}
      </h1>
      <p style={{ fontSize: '1rem', lineHeight: 1.65, color: '#394b41', marginBottom: '28px' }}>
        {content.subtitle}
      </p>

      <div style={{ display: 'grid', gap: '16px', marginBottom: '26px' }}>
        {content.cards.map((card) => (
          <section
            key={card.heading}
            style={{
              background: '#ffffff',
              border: '1px solid rgba(20,56,42,0.14)',
              borderRadius: '14px',
              padding: '20px 22px',
              boxShadow: '0 4px 16px rgba(16,40,30,0.04)'
            }}
          >
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.18rem',
                color: '#0B3A26',
                marginBottom: '10px'
              }}
            >
              {card.heading}
            </h2>
            <ul style={{ margin: 0, paddingInlineStart: '20px', display: 'grid', gap: '8px', color: '#2b3c33', fontSize: '0.92rem', lineHeight: 1.6 }}>
              {card.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <section
        style={{
          background: '#f7f5ee',
          border: '1px solid rgba(184,133,40,0.35)',
          borderRadius: '14px',
          padding: '18px 22px',
          marginBottom: '24px'
        }}
      >
        <h2 style={{ fontSize: '1.05rem', color: '#14382a', marginBottom: '6px' }}>
          {content.grievanceTitle}
        </h2>
        <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.6, color: '#35453d' }}>
          {content.grievanceBody}
        </p>
      </section>

      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <Link
          to="/profile"
          className="btn-primary-forest"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}
        >
          <IconCheck size={15} />
          {content.ctaProfile}
        </Link>
        <Link
          to="/"
          className="btn-orange-outline"
          style={{ display: 'inline-flex', alignItems: 'center', textDecoration: 'none' }}
        >
          {content.ctaHome}
        </Link>
      </div>
    </main>
  );
}
