'use client';

import { React, useState } from 'react';
import { Plane, User } from 'lucide-react';

const NavBar = () => {
	const [menuOpen, setMenuOpen] = useState(false);
	const [selectedTab, setSelectedTab] = useState('Search');

	return (
		<div className='fixed top-0 left-0 right-0 w-full z-50 h-12  bg-white shadow-sm'>
			<div className='justify-between items-center flex flex-row '>
				<div className='flex flex-row gap-2 pl-2'>
					<Plane className='bg-blue-600 text-white rounded-md p-1 '></Plane>
					<h1 className='flex flex-row font-bold'>Take-Off Tracker</h1>
				</div>
				<div className='flex gap-10 pr-10'>
					<button
						onClick={() => setSelectedTab('Search')}
						className={`px-3 py-2 text-sm font-medium ${
							selectedTab === 'Search'
								? 'text-blue-600 border-b-2 border-blue-600 font-bold'
								: 'text-gray-500 hover:text-gray-700'
						}`}>
						Search
					</button>
					<button 
                    onClick={() => setSelectedTab('Alerts')}
                    className={`px-3 py-2 text-sm font-medium ${
                    selectedTab === 'Alerts'
                    ? 'text-blue-600 border-b-2 border-blue-600 font-bold'
								: 'text-gray-500 hover:text-gray-700'
						}`}>
						Alerts
					</button>
					<button 
                    onClick={() => setSelectedTab('History')}
                    className={`px-3 py-2 text-sm font-medium ${
                        selectedTab === "History"
                        ? 'text-blue-600 border-b-2 border-blue-600 font-bold'
                            : 'text-gray-500 hover:text-gray-700'
                    }`}>
						History
					</button>
				</div>
			</div>
		</div>
	);
};

export default NavBar;
