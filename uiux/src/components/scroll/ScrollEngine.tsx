import React from 'react';
import { motion } from 'motion/react';

interface ScrollSectionProps {
  children: React.ReactNode;
  id?: string;
  className?: string;
}

export const ScrollSection: React.FC<ScrollSectionProps> = ({ children, id, className = '' }) => {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0.88, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      className={`relative z-10 ${className}`}
    >
      {children}
    </motion.section>
  );
};
